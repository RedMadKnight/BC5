# 0414 — EmuFive survey: what to port, what we did differently

**Question.** The maintainer's order: "EmuFive - zrób rozeznanie co możemy skopiować z tego projektu i jakie błędy
popełniliśmy w naszym". What in EmuFive (and the emulator it ships) can we port into patch 0001 / `backend/`, and
where does its design differ from ours in a way that could explain our known problems (the ~11.9 GiB pinned wall,
the orphan release's cut-and-return churn, the `pending_events` leak, the single device mutex, RT hangs)?

Labels used below: **[S]** read in source (path:line@commit), **[I]** inferred, **[M]** measured by us earlier
(experiment or F-row cited).

## Setup

Laptop only; no box access. Nothing built or run from the downloaded code.

- Search: WebSearch for "EmuFive PS5 emulator github" (no hit by that name; the press covers sharpemu/KytyPS5), then
  the GitHub search API `search/repositories?q=emufive`: two repositories.
  - `blue0x1/EmuFive` — "A PS5 emulator for the PS4. Runs on a jailbroken PS4 with Linux, installed through PS4
    Multiboot." GitHub licence GPL-2.0, created 2026-11-09, last push 2026-11-11 14:49 UTC, 201 stars, 9 forks.
    **This is the PS5 project.**
  - `MrKitsune9/Orbis-EMUFIVE` — one 3.5 KB `README.md`, no licence, no code. Skipped.
- Clones (in `C:\Users\kjani\Downloads\bc5\refs\`, each in its own new directory):
  - `blue0x1_EmuFive`: full clone, HEAD `40bff0bf143829a00773d40839bce32710e4cefa` (2026-11-11 17:48 +0300).
  - `KytyPS5_KytyPS5_full`: blobless full clone of `https://github.com/KytyPS5/KytyPS5`, because EmuFive pins
    KytyPS5 `589bd14a9b8934a85e951d1aaa8112a05d62354c` (2026-11-07) and the older reference clone
    (`KytyPS5_KytyPS5`, shallow at `4644c52`, 2026-10-21) does not contain it. Upstream HEAD at survey time:
    `bc934ef0` (2026-11-11), 45 commits past the pin.
- Our side: BC5 main `262cf68c` (read, not switched); patch line numbers below are `P:<line>` in
  `backend/kytyplus-patches/0001-bc5-lle-agc.patch` on that commit. KytyPlus base f266548; where f266548 itself was
  not available on the laptop, the lines are from the reference clone `Coder787-source_KytyPlus` at `3eee96a` and
  marked so.
- Earlier surveys not repeated: 0402 (KytyPS5 up to `dfec14a`, 2026-11-02), 0405 (port decisions of 11-04).
  For KytyPS5 only the 119 commits `dfec14a..589bd14` (the part EmuFive ships that 0402 did not see) and a short
  look at the 45 after the pin were read.

## Result

### 1. Identity, licence, provenance

**What EmuFive is** [S]. Not an emulator of its own: a Debian system image for Linux on a jailbroken PS4 (PS4
Multiboot), which builds **upstream KytyPS5 at a pinned commit plus seven patches** and wraps it in a home screen.
`scripts/build-kyty.sh:17-18@40bff0b` (`KYTY_URL=https://github.com/KytyPS5/KytyPS5.git`,
`KYTY_COMMIT=589bd14a…`); `:39-41` apply `patches/kytyps5/*.patch`. The GPU path is Vulkan through the PS4's Mesa
(RADV on Liverpool/Gladius); the CPU is the PS4's Jaguar.

| Item | Finding |
|---|---|
| Repository | https://github.com/blue0x1/EmuFive |
| Licence | `LICENSE` = GNU GPL version 2 text; GitHub SPDX `GPL-2.0`. Files carry "Copyright (C) 2026 Chokri Hammedi (blue0x1)" with no "or later" grant, so treat as GPL-2.0-only. KytyPS5 at the pin: `LICENSE` is GPL-2.0 too (`git show 589bd14:LICENSE`). Both are compatible with our GPL-2.0 KytyPlus patch. |
| Activity | 28 commits, 2026-11-07 → 2026-11-11, one contributor (blue0x1 / Chokri Hammedi, 28 commits). 84 tracked files. |
| Size of its own code | 7 KytyPS5 patches, 4,194 lines in all (0001 88, 0002 1,177, 0003 522, 0004 1,858, 0005 145, 0006 55, 0007 349); a Jaguar test harness (530 lines); ~11,000 lines of Python/shell for the home screen, launcher, swap, Bluetooth, USB and updates. |
| Provenance | **Clean** [S]. Each patch is the author's own work on top of GPL KytyPS5, with a prose rationale. No Sony headers, no SDK names beyond the import names every emulator uses (one `sceUserServiceGetForegroundUser` in 0003), no decompiler output, no hard-coded game addresses (grep for `sub_`, `loc_`, 9+-hex-digit constants: only an IEEE sign mask in 0004). `tools/extract-code.py` reads the executable segments of a user-supplied SELF/ELF for the author's own test harness; it ships no game data. The PS4 kernel, its firmware blobs and the jailbreak come from PS4 Multiboot, outside the repo (`docker/rootfs.Dockerfile:1-6`), and nothing of that is relevant to us. |
| Provenance of the base | KytyPS5 (GPL-2.0), already accepted as a source in 0402; the 119 commits read here are by its usual contributors (nmzik 99, superkeka, TheCruZ, Artyom Zabroda, ...), small and self-described. |

**Verdict on Q1's precondition:** licence and provenance are fine; ports are allowed. But EmuFive's own code
targets a different machine (Jaguar CPU without AVX2; GCN GPU through RADV), so almost all of what is worth taking
comes from **the KytyPS5 commits it ships** (`dfec14a..589bd14`), not from its seven patches.

### 2. Q1 — what we can copy or port

Effort: S < 50 lines / under a day; M 50–300; L > 300. "Match" = we already do the same.

| # | Their file / function (commit) | What it does | Our matching place | Port size | Licence / provenance | Do we match? |
|---|---|---|---|---|---|---|
| 1 | KytyPS5 `src/kernel/semaphore.cpp:54-59, 91, 125, 170-176, 226 @589bd14` (commit `a0268f1`, "a semaphore signal wakes only the waiters it hands counts to") | Each waiter sleeps on its own `CondVar`; `WakeWaiters` signals only the waiters it gave counts to; the shared `m_cond_var.SignalAll()` in Signal/Cancel/dtor is gone. 31 lines changed. | KytyPlus `src/kernel/semaphore.cpp` (via patch 0001; P:25347 touches only a log line). Ref clone `3eee96a:src/kernel/semaphore.cpp:66, 94, 129, 149, 234-236` still has the one shared `m_cond_var` with `SignalAll` | S (~30 lines, same `Common::CondVar` API in KytyPlus) | GPL-2.0, clean | **No.** This is exactly F451's convoy (exp 0358: "`KernelSemaPrivate::Signal` broadcasts the semaphore's single condition variable ... the console wakes only the thread it gives the count to"). Our A12 `KYTY_BC5_SEMA_FIXES` (0401 e5, `thr0405-notes.md`) ported attributes/counts and KK06 notify-under-lock, not this. |
| 2 | KytyPS5 `src/graphics/host_gpu/renderer/sync.cpp:79-94 @589bd14` (commit `c86d31b`, "coalesce repeated GPU interrupts with the same data") | When the event is already triggered, a new trigger whose data equals the newest undelivered entry only bumps that entry's `fflags`; a different data value still queues. | KytyPlus `sync.cpp` `EopEventTriggerFunc` (ref `3eee96a:src/graphics/host_gpu/renderer/sync.cpp:87` pushes unbounded) and `eventQueue.cpp:275` (AMPR). Our C1 `KYTY_BC5_EVENT_PENDING_CAP` (0412 §11, `events/event_cap0412.hpp`) | S (7 lines) | GPL-2.0, clean | **Partly.** C1 bounds the queue (tested: ASTRO BOT 217.8 → 0.1 MiB/min, 0412 §11) but is **not integrated into patch 0001** (`0413…/audit-unintegrated.md:77`). Their rule is gentler (no data loss when data differs) but unbounded when every trigger carries new data; KytyPS5 still pushes unbounded for user/AMPR events (`eventQueue.cpp:266@589bd14`). |
| 3 | KytyPS5 `src/graphics/presentation/videoOut.cpp:338-345 @589bd14` (commit `d6cec24`) | VideoOut event: one pending event counted in place, no `pending_events` copies. | Patch 0001 `TriggerVideoOutEvent` P:9201-9209 ("experiment 0188: while unread, one event, updated in place") | – | – | **Match** (we did it first, F246 / exp 0188). |
| 4 | KytyPS5 `src/graphics/shader/recompiler/backend/spirv/spirvEmitterMemory.cpp:189-191 @589bd14` (commit `6030fde`) | In BVH traversal shaders, a page no buffer backs reads as all ones (the absent-node link `image_bvh_intersect_ray` returns) instead of zero, "because guest list walks end on negative links and would advance over zero entries forever" (their comment). | No shader recompiler on our side (native ISA). The equivalent would be what an unbacked GPU VA reads as: today a NULL PRT / zero page (`BC5_DIRECT_AMM_PRT=1` in the launcher, 0408 §B) or a VM fault. | Idea only; an M-sized backend change (a 0xFF filler BO for the RT window) | GPL-2.0; the code itself does not transfer | **No.** See Q2 "Ray tracing". |
| 5 | EmuFive patch `0006-graphics-no-conditional-rendering-on-ps4-gpus.patch @40bff0b` (`vulkanWindow.cpp`) | On AMD 0x9920–0x9924 (Liverpool/Gladius) RADV's conditional rendering is turned off: "their command processor never finishes the SET_PREDICATION packet: the gfx ring times out, the GPU reset fails". Found with `RADV_DEBUG=hang`. Env override `KYTY_CONDITIONAL_RENDERING`. | Our policy NOPs `SET_PREDICATION` (`backend/policy/pm4-policy.tsv:11`, 0405 item 27 "changes GPU submission when on"); the second title's lake work has 0 predication packets (F721, F771). | Nothing to port (our GPU is not in that ID range; we do not use Vulkan) | GPL-2.0, clean | **Match in effect.** It is a hazard note for 0405 item 27 (see Verdict). |
| 6 | EmuFive patch `0005` (`KYTY_FPS_COUNTER`) | Flip-count FPS box. | `KYTY_BC5_FPS_COUNTER` (exp 0172, P:10453-10476) and the OSD fps (P:6270) | – | – | **Match.** |
| 7 | EmuFive patch `0003` (`KYTY_MOUNTS`, `emulator.cpp` `MountSandboxDirs`; LibcCompat dirent/lstat/realpath; `sceUserServiceGetForegroundUser`) | Extra host folders as guest paths; small libc functions for homebrew. | KytyPlus `emulator.cpp` mounts; no `KYTY_MOUNTS` in patch 0001 | S (mounts ~30 lines) / M (libc bits) | GPL-2.0, clean | No. Low value for us (homebrew); a candidate only under the "ports not title-gated" rule. |
| 8 | EmuFive patch `0002` (`src/libs/libcCompat.cpp`, ~1,000 lines; `runtimeLinker.cpp` binding) | An HLE C library used only when a module is the stand-in `libc.prx` of the ps5-native-app-boilerplate homebrew. | Nothing equivalent | L | GPL-2.0, clean; it is host code, not the title's libc, so 0405's "no title libc" does not forbid it [I] | No. Value only for homebrew. |
| 9 | EmuFive patches `0004` (`jaguarCompat.cpp`, AVX2/FMA/BMI2 → SSE/AVX rewrites) and `0007` (4-byte sites through a relay; cross-cache-line code patching with an invalid-opcode first byte and `membarrier(SYNC_CORE)`) | Run Zen 2 guest code on a Jaguar. | Not needed: the BC-250's Zen 2 has AVX2/FMA/BMI2 natively. | – | GPL-2.0, clean | **Match** (by hardware). The 0007 cross-line live-patching recipe is a technique note if we ever patch hot guest code at run time [I]. |
| 10 | EmuFive `tools/jaguar-test/jaguarTest.cpp @40bff0b` | Differential test: each instruction form found in real code runs natively and as its replacement from one random register/flag/memory state; everything must match. | Our CPU tests (e.g. `memfast/*.cpp`, `thr0405`) | Pattern only | – | Idea for any future guest-code rewrite (e.g. 0402's TSC patching). |
| 11 | EmuFive `overlay/opt/ps5-on-ps4/bin/ps5-launch:26-76` (memory watchdog) and `bin/ps5-swap` (4 GB swap file, `vm.swappiness=10`) | Kill the game (SIGTERM, 5 s, SIGKILL) when MemAvailable + SwapFree < 160 MB for 3 s; swap as a safety net. | Our watchdog / fuse (`memory.max` 12,400 MiB, 0412 §§ on the fuse), zram swap on the box | – | – | **Match / ahead.** |
| 12 | EmuFive `overlay/etc/wireplumber/wireplumber.conf.d/51-ps5-hdmi.conf` | Ranks a USB DualShock 4's sound card below HDMI so game sound does not go to the pad. | Our audio follows the controller's device on purpose (haptics on channels 3–4, F69, F79; P:4353-4495) | – | – | **Do not copy:** it would send the pad's haptics stream to the TV. |
| 13 | KytyPS5 after the pin (not in EmuFive): `fc1369e6` "split memory locking into an operation lock and a shared state lock", `1b59ee62` "read guest backing through a lock-free page table", `937b3766` "present without holding the port locks", `f399d481` "run guest threads and fibers with the console's FP environment" | Lock splitting in the memory manager; FP environment (MXCSR/x87) at thread and fiber start. | Device-mutex design (`0412 DESIGN-device-mutex.md`); our x87 0x037f fix (A12) | M–L each | GPL-2.0 | Ideas for the device-mutex work; `f399d481` worth a diff against A12 (not read in detail here). |

### 3. Q2 — where their design differs from ours

#### 3.1 Memory: what is pinned for the GPU; direct vs flexible; how memory is returned

*Theirs* [S]:
- Guest direct memory is one `memfd` sized to the budget (`src/kernel/memoryAddressSpace.inc:107-119@589bd14`:
  `memfd_create("KytyDirectMemory")`, `ftruncate`, one `MAP_SHARED` alias); guest views are `MAP_SHARED|MAP_FIXED`
  maps of it (`:459`). Pages exist only once touched.
- Budget: `GUEST_MEMORY_BUDGET` 12,800 MiB, a 64 MiB cache off the top, flexible 448 MiB default or
  `param.json`'s value, page-table overhead subtracted (`src/kernel/memory.cpp:63-77, 965-977@589bd14`; 0402
  item 5 already lists this).
- **Nothing of guest memory is pinned or imported for the GPU.** A GPU "mapping" is bookkeeping:
  `RenderContext::MapMemory` adds the range to `m_mapped_ranges` and queues a BDA sync
  (`src/graphics/host_gpu/renderer/renderContext.cpp:92-96@589bd14`); data reaches the GPU through Vulkan buffer
  and texture caches that copy and track dirtiness. No `mlock`, `MAP_LOCKED`, udmabuf or
  `VK_EXT_external_memory_host` anywhere in `src/` (git grep @589bd14). (EmuFive still sets `memlock unlimited`,
  `overlay/etc/security/limits.d/90-kytyps5.conf`; what uses it is not visible in KytyPS5's source [I: RADV or
  nothing].)
- Unmap: `RenderContext::UnmapMemory` (`renderContext.cpp:98-127@589bd14`) runs **on the GPU thread**
  (`m_gpu->SendCommandSync(unmap)`, :127); it drains the GPU (`Finish` + `WaitPriorityOperations`, :108-113) only
  when the range has cached buffer/texture data or priority work is pending, then invalidates the caches.
- Returning memory: no `fallocate(PUNCH_HOLE)` or `MADV_REMOVE` in `src/` @589bd14, so released direct memory's
  pages stay in the memfd until reused — the same as ours (P:25011, 0408 §B). The difference is that theirs are
  ordinary shmem pages, swappable; EmuFive adds a 4 GB swap file because "Linux on the PS4 has about 6 GB"
  (`bin/ps5-swap:4-7`).

*Ours* [M]: one pinned memfd shared through udmabuf, eager import of whole GPU heaps (10,047 MiB, 90 % of the pin,
F353), 2.8–3.7 GiB of it zero chunks (0412 §1), pinned total only grows (F623); ~11.9 GiB pinned at the wall with
RT on (F688's "11,930 MiB logged as pinned"; 0412 §§16, 29). 0408 (`README.md:434`) rejected copying into device
buffers, userptr, KFD SVM and an LRU of imports, for reasons that still hold (native ISA reads guest VAs directly;
a re-import miss is a 14-s fault).

*Measurable consequence* [I]: the console's model and KytyPS5's both leave untouched pages unbacked; we back and
pin them. That is the 2.8–3.7 GiB of zero chunks, the largest single lever 0412 measured ("the lever is the zero
skip", 0412:444; zero skip + orphan release 0.55–0.75 GiB less pinned, 0412:425). KytyPS5 runs a 12.5 GiB guest
budget on a ~6 GB machine (EmuFive README: Sons of Sparta at ~40 FPS on a PS4 Pro) because of demand paging plus
swap — a small title, so this shows the model, not a number for ours.

*Proposed fix*: not a port. Make the zero skip (already built, 0412 arm `zo`) the default route rather than an arm,
under its existing switch; no new switch.

#### 3.2 The orphan release "ping-pong" (cut, returned, cut again)

*Theirs* [S]: a GPU "map" is a range insert plus a queued BDA sync (`renderContext.cpp:92-96`), so a heap that
breathes costs them a cache invalidation, not a re-import; and the unmap runs on the GPU thread in submission
order (`:127`), never under a lock that guest submitters wait on.

*Ours* [M]: 0412 §27 — the lazy release cut 1,422 MiB and 1,486 came back under views; each return is an import
and a mapping rebuild under `g_dev_mutex`; one cut started 1.55 s of holds across three threads. The
return-aware release (`BC5_GUARD_RETURN_EXEMPT`, 0412 §28, arm fast3) is our answer to the churn.

*Consequence / fix*: their model has no ping-pong because re-mapping is cheap and off the submit lock. The
transferable part is **where** the work runs: do the cut and the re-import on one owner thread in submission order
instead of inside whichever submitter holds the mutex — this is stage 1 of `DESIGN-device-mutex.md`, see 3.3. Keep
`BC5_GUARD_RETURN_EXEMPT` as the cheap fix meanwhile.

#### 3.3 GPU submit path and locking (our single device mutex)

*Theirs* [S]: `GuestGpu::Submit`/`SubmitCompute` only build a `Submission` and `Enqueue` it under a short
`m_queue_mutex` (`src/graphics/guest_gpu/graphicsRun.cpp:112-133, 372-378@589bd14`). One GPU thread
(`ThreadRun`, :388-480) takes work round-robin from the gfx queue and the compute queues, runs host commands sent
with `SendCommand` (memory unmaps among them, :71-81) before submissions, and **re-queues a submission that cannot
complete** (`blocked = true`, pushed back to the front, :465-471) instead of sleeping on it. Guest threads never
hold a lock while host GPU work runs.

*Ours* [M]: every submitting thread (`bc5-ring`, Render Thread, `bc5-chainwd`) runs `submit_now` entirely under
`g_dev_mutex` (P:28555, P:33755): probe, mapping sync, learned windows, filters, CS ioctl. Held 45 % of wall
time; 35 s of waits in 180 s; single holds 35–135 ms, peaks 354–1,501 ms (0412 §20); the mapping maintenance has
the long holds (847/606/217 ms, §21); long holds cover 27 % of >100 ms frame gaps, 44 % in play (§22).

*Consequence* [I]: the mutex turns three producers into one at a time, and a long mapping sync stalls the Render
Thread's submit. KytyPS5's shape (enqueue, one owner) moves that wait off the guest threads; the owner still does
the same work serially, so the gain is bounded by §22's 27–44 % share of gap time — single percents in mean fps,
more in hitch count (0412 §21's estimate stands).

*Proposed fix*: `BC5_DIRECT_SUBMIT_OWNER=1` (default off): submitters copy what needs only the buffer (probe,
filter, hints) outside any lock, then enqueue; one `bc5-submit` thread owns `g_dev`, the mapping sync, the release
cuts and the CS ioctl, in enqueue order. Keep the existing per-ring ordering and the in-flight cap (P:33745-33754).
Size L; needs its own design review (it is DESIGN-device-mutex stages 1–2 with a different owner model).

#### 3.4 Event queues (`pending_events`)

*Theirs* [S]: VideoOut — one event counted in place (`d6cec24`, `videoOut.cpp:338-345`); GPU interrupts — a
repeat with the same data bumps the newest entry (`c86d31b`, `sync.cpp:84-94`); user/AMPR events — still an
unbounded `push_back` (`eventQueue.cpp:266@589bd14`).

*Ours*: VideoOut match (P:9201-9209, exp 0188). EOP and AMPR: the unbounded `push_back` of KytyPlus; ASTRO BOT
grew 217 MiB/min in `bc5-cq0` through `EopEventTriggerFunc` (0412 §10–11) and the shared build was killed after
36 min on 11-10 (`audit-unintegrated.md:77`). Our C1 cap fixes it (0.1 MiB/min) but sits outside patch 0001.

*Consequence*: the leak is still in the shipped patch; neither project bounds user/AMPR events.

*Proposed fix*: integrate C1 into patch 0001 as is (`KYTY_BC5_EVENT_PENDING_CAP=<n>`, default off), and add
KytyPS5's same-data coalesce as a first stage of the same function under `KYTY_BC5_EVENT_COALESCE_SAME=1`
(default off), so a title that waits less often than the GPU interrupts loses no distinct data until the cap is
reached. S.

#### 3.5 Semaphores and worker wake-ups

*Theirs* [S]: per-waiter condition variables, targeted wake (`a0268f1`, `semaphore.cpp:54-59, 170-176, 226`).

*Ours* [S, ref clone `3eee96a`]: one `m_cond_var`, `SignalAll` on every signal (`semaphore.cpp:66, 94, 129, 149`);
F451 (exp 0358) names the convoy as a candidate for idle Hi workers.

*Proposed fix*: port `a0268f1` behind `KYTY_BC5_SEMA_TARGETED_WAKE=1` (default off). S. Measure: worker idle share
and frame time on the scripted load (0412's arm fast3 as baseline). Expected gain [I]: small to medium; it removes
wake-ups, not GPU time.

#### 3.6 Shader and command-buffer handling

*Theirs*: HLE — PM4 parsed on the host, GCN/RDNA shaders recompiled to SPIR-V, caches for buffers/images, global
load base pages backed before compute dispatches (`c174ade`). *Ours*: LLE — the title's own command buffers and
native shaders, filtered by policy and run on the real CP. Nothing of their recompiler or caches ports (0405
reached the same conclusion for AnyPS5/KytyPS5). The one transferable idea is c174ade's: back what a dispatch's
base pages need at dispatch time, which our learned windows and hints already do [I, match in spirit].

#### 3.7 Ray tracing

*Theirs* [S]: BVH traversal shaders read unbacked pages as `~0` (`6030fde`, `spirvEmitterMemory.cpp:189-191`),
because a zero link sends the guest's list walk round forever; a missing node must read as "absent".

*Ours* [M]: every RT hang caught so far stops inside the title's BVH work (F336), with TCP read faults just before
the gfx timeout (F336: 0x1334f81000; F582: a TCP read by program 0x909977100, the adjacency build in the
0x0909 RT/BVH window, at an address in none of the title's direct mappings). Unbacked GPU VAs read as zero for us
(NULL PRT on `BC5_DIRECT_AMM_PRT=1`, or the fault path) [I: what a faulting load returns with retry off was not
re-read here].

*Consequence* [I]: if a BVH walk reads a link from a page we left unbacked, zero is a valid-looking link and the
walk need not end — a hang, matching F336's order (read fault, then timeout). KytyPS5 hit the same failure in its
own model and fixed it with all-ones. This is a hypothesis, not shown for our title.

*Proposed fix*: `BC5_DIRECT_UNBACKED_FILL=ff` (default off): back unbacked pages that the RT/BVH programs touch
(the learned window list, or faulting VAs in the 0x0909 window) with a shared read-only BO filled with 0xFF instead
of a zero/NULL PRT page. First a catcher: log the VA and program of every TCP read fault with RT on, and whether
it lies in a heap we deliberately do not import. M. Test with RT on (standing rule), against F336/F582's bench.

#### 3.8 Audio

*Theirs*: KytyPS5's audio stack; at the pin only stubs added (voice chat `589bd14`) and NGS2 pan/reverb
(`53362105`); EmuFive routes sound to HDMI over a USB pad (`51-ps5-hdmi.conf`). *Ours*: AudioOut2 haptics to the
controller with device-follow on replug (P:4353-4495, F69, F79, F93). We are ahead; nothing to port. NGS2
(`53362105`) only if a title of ours uses NGS2 [not checked here]; any audio change needs the DualSense replug
check.

#### 3.9 Save data

*Theirs*: nothing new in `dfec14a..589bd14` beyond `4543714` (paths through GetInfo, a refactor); EmuFive keeps
saves per profile (`ps5-launch:103`, `--user-id`). *Ours*: 0402 item 9 already lists KytyPS5's save fixes. No
new item.

## Verdict

EmuFive (`blue0x1/EmuFive`, GPL-2.0, clean provenance, 28 commits by one author in 5 days) is a PS4-Linux
packaging of **KytyPS5 `589bd14` + 7 patches**. Its own patches solve problems we do not have (Jaguar CPU, GCN
predication hang, homebrew libc). The useful material is in the KytyPS5 commits it ships, and the main lesson is
design: they never pin guest memory and never hold a lock across host GPU work on guest threads.

Ranked by expected gain for us:

1. **Integrate the events cap (C1) into patch 0001, plus same-data coalescing** (`KYTY_BC5_EVENT_PENDING_CAP`,
   new `KYTY_BC5_EVENT_COALESCE_SAME`). A measured 217 MiB/min leak that killed the shared build; the fix is
   ours and tested; KytyPS5 `c86d31b` confirms the diagnosis independently. S.
2. **Zero skip as the default memory route** (existing switch). KytyPS5/the console leave untouched pages unbacked;
   our pinning of 2.8–3.7 GiB of zero chunks is the biggest measured lever on the wall (0.55–0.75 GiB with the
   orphan release). No new code.
3. **RT: unbacked BVH reads as all ones** (`BC5_DIRECT_UNBACKED_FILL=ff`, catcher first). Only a hypothesis, but
   it names a mechanism for the open RT hangs that fits F336/F582's fault-then-timeout order. M.
4. **Submit owner thread** (`BC5_DIRECT_SUBMIT_OWNER=1`), KytyPS5's enqueue-plus-one-GPU-thread shape for our
   device mutex and the release cuts. Bounded by 0412 §22 (27–44 % of gap time); L, needs its own review.
5. **Targeted semaphore wake** (`KYTY_BC5_SEMA_TARGETED_WAKE=1`, port of `a0268f1`). F451's convoy; S; gain
   unknown until measured.
6. Low: `KYTY_MOUNTS` (0003), the homebrew libc (0002), a diff of KytyPS5 `f399d481` (FP environment) against our
   A12 x87 fix, KytyPS5 `fc1369e6`/`1b59ee62` lock splitting as reading for the device-mutex design.

Not to copy: 0004/0007 (Zen 2 has the instructions), 0006 (other GPU), the WirePlumber HDMI rule (breaks haptics).
For 0405 item 27 (`SET_PREDICATION` behind a switch), EmuFive 0006 is a warning that a CP can stall on it with a
failed reset on GCN; our GPU is not in that ID range, but the test of that item should run with hang breadcrumbs.

**Not verified:** KytyPlus `f266548` itself (semaphore/sync lines are from the `3eee96a` reference clone); what
`memlock unlimited` serves in EmuFive; what a faulting GPU load returns on our box with retry off; whether the
second title uses NGS2; the RT hypothesis (3.7) on the box; the gain of 3.3 and 3.5. No box access, nothing built.
