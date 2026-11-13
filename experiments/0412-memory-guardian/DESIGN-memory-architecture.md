# DESIGN: the memory architecture, against other emulators (exp 0412, 2026-11-12)

The maintainer's question: why do other emulators not hit a memory wall, why does a PS4 emulating a PS5 with fewer
resources not hit it either, what do they do better, and does ours need rebuilding.

Marks: [S] read in source at the commit named; [M] measured by us (section of this README or F-number in
`docs/HANDOFF.md`); [I] inferred. Nothing here was run; the first experiment is at the end. This note does not defend
the current design.

## 1. The short answer

- **They copy and translate; we share and pin.** Every emulator read here keeps guest RAM as ordinary swappable
  shared memory, recompiles the guest's shaders, and gives the host GPU *copies* of the ranges a draw actually uses.
  The host GPU never sees a guest address, so the emulator always knows exactly which guest bytes the GPU needs, and
  everything else can stay unbacked or go to swap. That is why they have no wall. Their price is CPU time (copies,
  hashing, write-protect faults, read-backs that stall on the GPU) and a second copy of whatever the GPU uses.
- **We feed the title's own command buffers and native shaders to the GPU.** Shaders compute addresses; nothing
  translates them. So the GPU's address space must hold the guest's memory at the guest's addresses, resident,
  *before* any job runs, and nobody can tell in advance which pages a job will touch (sections 39 and 48: searches by
  value miss; the title's protection bits do not say). The console is in the same position and solves it the same
  way: the title's memory is simply resident. Our real differences from the console are three, and they are ours:
  1. **Our import creates pages the title never touched.** `udmabuf` allocates every hole of the range it covers
     and long-term pins it [S, section 3]. 3.5 GiB of the pinned memory are pages of zeros [M, section 39]. (The
     console also commits that memory physically [I]; it has it. We do not.)
  2. **Our pin makes CPU-only data unswappable too**, because we import every direct-memory heap whole.
  3. **We run a desktop Linux, a driver and an emulator in the space where the console has a small system
     reserve**: 3.2–3.6 GiB against a budget that leaves 3.2 [M, section 16]. The deficit is 0.4–0.5 GiB.
- **The PS4 case** (EmuFive = upstream KytyPS5 at a pinned commit plus seven patches, on Linux on a jailbroken PS4;
  exp 0414): it never pins; guest memory is a memfd, pages exist once touched, and the image adds a 4 GB swap file
  because "Linux on the PS4 has about 6 GB" [S, 0414 §3.1]. The published result is a small 2D-class title at about
  40 fps on a PS4 Pro. It shows the model works where a title touches little memory; it says nothing for a title that
  commits and uses 12 GiB. Such a title would live in swap there.

So: the others are not better at holding 12 GiB; they never have to hold it for the GPU. A rebuild to their model is
a different emulator (section 5, option D). What we must fix is the three points above.

## 2. How the others hold memory (from source)

| Project (commit) | Guest RAM | What the GPU gets | CPU writes found by | GPU writes returned by | Shaders |
|---|---|---|---|---|---|
| shadPS4 `b97bafa3` | one `memfd` (`core/address_space.cpp: AddressSpace::Impl`), views `MAP_SHARED`; no host `mlock` | copies: one sparse Vulkan buffer per 4 GiB of guest space, device memory bound on first use in ≥16 KiB blocks (`buffer_cache.cpp: EnsureResident`); dirty ranges copied at bind time (`SynchronizeMemory`); small buffers re-copied every use into a 128 MiB stream buffer; textures in an LRU cache trimmed at 1.5/3 GB (`texture_cache.cpp: GarbageCollectImages`). The buffer arenas are never freed | `mprotect` + SIGSEGV per 4 KiB page (`page_manager.cpp`), optional userfaultfd | read-backs, **off by default** (`readbacks_mode` Disabled): GPU writes are then not returned at all | recompiled to SPIR-V; pointers resolved on the CPU (`ObtainBuffer`) |
| RPCSX `e8ae1481` | a shm file per process, mapped again by the GPU side (`rpcsx/vm.cpp`, `gpu/Device.cpp: mapProcess`) | copies into Vulkan buffers and images (`gpu/Cache.cpp`) | page flags + `mprotect` through a bridge thread; version tags per range | flush on a fault on a locked page: submit, wait, memcpy back (`Device.cpp` cache-update thread); the faulting guest thread spins meanwhile | `gcn` → SPIR-V |
| RPCS3 `9b8974d3` | memfd/shm | texture cache sections; vertex and index data copied **every draw** into ring heaps (`VK/VKVertexBuffers.cpp`) | page protection or a hash per section (`texture_cache_utils.h: buffered_section`) | flush on fault (`texture_cache.h: flush_all`) | recompiled |
| yuzu line (Eden mirror `e9661b2a`) | memfd + a fastmem arena (`common/host_memory.cpp`) | buffer and texture caches with a memory budget and garbage collection (`texture_cache.h: RunGarbageCollector`, about 1.1/1.6 GiB thresholds, target 3–4 GiB) | per-page bit words, write-protect of the fastmem arena (`buffer_cache/word_manager.h`, `core/memory.cpp`) | `FlushRegion` → download → write to guest | recompiled |
| Kyty `4733b7e1` (2022), and KytyPS5 `589bd14a` per exp 0414 | plain memory; KytyPS5: memfd `KytyDirectMemory`, no pin, no punch | copies (`Graphics/Objects/GpuMemory.cpp: CreateObject`, vertex `memcpy`, texture detile) | **XXH64 over the whole guest range, per submit** (`GpuMemory.cpp:582`); no page protection | `WriteBack` per object | recompiled |

Common pattern [S]: guest RAM stays reclaimable in all of them; the GPU owns copies; the two directions are kept in
step by faults, tags or hashes. None publishes a resident-set figure for a heavy title in the files read (not
searched further). What it costs them is visible in the code: a copy per upload, a signal and an `mprotect` per first
write to a watched page, a GPU drain per read-back, a full hash per submit in Kyty. shadPS4's default even gives up
correctness for speed (GPU writes are not returned).

## 3. Ours, stated plainly

- The title's direct memory is one memfd. Ranges under a view are turned into `udmabuf`s (64 MiB each by the module's
  default) and imported into amdgpu as dma-buf BOs, mapped at GPU VA = guest VA (patch 0001, "Direct submission",
  P:28690 ff.). The guest's small anonymous areas go as userptr BOs.
- **The property that forces residency:** GPU VA = guest VA with no translation, because pointers live inside the
  title's command buffers, tables and native shaders, and shaders compute more. The GPU has no demand paging: on
  this kernel a GPU access to an unmapped page is a logged fault, and here a 14 s freeze (2 s fence timeout + 12 s
  reset wait, F53) or worse (F6). A missing page cannot be fetched on fault.
- **What udmabuf does on top of that** [S, kernel v6.19 `drivers/dma-buf/udmabuf.c: udmabuf_pin_folios` →
  `mm/gup.c: memfd_pin_folios`; v7.1 unchanged; the box runs 7.2, not read]: every folio of the range is pinned with
  `FOLL_PIN` under long-term-pin rules for the udmabuf's life, and **a hole in the file is allocated at create time**
  (`memfd_alloc_folio`). The imported BO is `ttm_bo_type_sg`, external: TTM never swaps it and it is outside
  `ttm.pages_limit`. Punching a hole under a live udmabuf frees nothing [I].
- Numbers [M]: 12,024 MiB pinned at the wall of 15,193 (section 16). Command buffers name 918 MiB of it by the play
  phase, 314 MiB in any 10 s (section 34). 3,571 MiB are 4 KiB pages of zeros (section 39). 320 MiB are orphans
  (section 16). Up to 1.6 GiB are heaps no GPU work was seen to name at all and that are the CPU's by purpose
  (`AssetHeap` 1,166, `Wwise` 220, `Physics` 192; sections 34, 39). `AMM` (2,966) is reached only through shaders: the
  catchers are blind there.
- **What is provably never touched by the GPU: nothing, by the means we have.** "Reads zero when listed" failed
  (section 48: GPU writes arrive later). "No GPU protection bit" failed (section 39). "Not named by value" is
  incomplete (sections 39, 48). Only two classes are safe by construction: memory under no view (orphans), and
  memory no GPU mapping covers because the title never mapped it.

## 4. What the kernel offers (amdgpu, v6.19 read, v7.1 diffed)

- **userptr BOs are not pinned** [S, `amdgpu_ttm.c: amdgpu_ttm_tt_get_user_pages` → `hmm_range_fault`; no
  `pin_user_pages`]. The pages stay ordinary LRU pages; an MMU notifier (`amdgpu_hmm.c: amdgpu_hmm_invalidate_gfx`)
  waits for the BO's fences when the kernel takes one. But **every submission re-faults every userptr BO in its BO
  list** (`amdgpu_cs.c: amdgpu_cs_parser_bos`), which swaps in whatever was swapped out, and costs a full page walk:
  we measured 5 ms per GiB per submission (F38, F54). A BO left out of the list keeps stale GPU mappings after
  reclaim on v6.19 (on v7.1 the notifier also invalidates the VM mapping). So userptr gives "reclaimable" only for
  BOs a submission does not list, and then the GPU must not touch them: the discovery problem again.
- **GPU-owned BOs mapped into the guest are less reclaimable, not more** [S, `ttm_bo.c: ttm_bo_swapout_cb`,
  `ttm_tt.c`]: TTM swaps a BO only when its own page limit is exceeded, never on system memory pressure.
- **PRT mappings** (`AMDGPU_VM_PAGE_PRT`, `gmc_v10_0_get_vm_pte`): a GPU VA range with no backing; the usual
  semantics "reads give zero, writes are dropped, no fault" are **not stated in the driver** [I]. `AMDGPU_VA_OP_REPLACE`
  swaps a range between a BO and PRT without a hole [S]. We already use a PRT window (0408 item 5).
- **Read-only mappings**: without `AMDGPU_VM_PAGE_WRITEABLE` a GPU write raises a write-protection fault
  (`gfxhub_v2_0`, enabled by default) [S/I]; the last fault's address and status can be polled with
  `AMDGPU_INFO_GPUVM_FAULT` [S]. No event, no queue, the job is not paused. What such a fault costs on gfx1013 (a log
  line, or F53's 14 s) is not known.

## 5. Options

| | Option | What must be rebuilt | Expected saving | Risk | First measurable step |
|---|---|---|---|---|---|
| A | **The console's budget: shrink everything that is not the title** — a play session without Plasma's shell; the host's own copies beside the guest (DMA snapshot ring 64, staging 96, tiler pool 96–128, RADV 117 MiB; section 1); the driver buffers outside the guest (583 MiB, not broken down); orphans (320); then offer the title the console's 12,800 MiB instead of 13,824 | nothing architectural; a session file; a per-client `fdinfo` breakdown; the host bugs that kill runs at smaller offers (section 3 of the README) | 0.4–0.5 GiB (session) [I] + up to 0.3 (host copies, to be measured) + 0.3 (orphans) [M] + unknown (offer) = **0.7–1.1 GiB** before the offer | low | `snap0412.sh` with `fdinfo` lines at the wall, once in Plasma and once in a bare session (his decision to try) |
| B | **Do not create pages nobody wrote, soundly** — never-written memory gets no udmabuf; the GPU sees zeros there through a read-only zero mapping or PRT (no aliasing: the shared canary slice is what turned lost writes into garbage, section 48); memory comes back *before* a write, from exact knowledge of GPU write targets (render targets and depth from registers, copy and DMA destinations from packet operands, RW buffers and images from the descriptor tables), with the write fault as a detector that names the address | the zero skip's trigger and its canary; a write-target tracker in the submit path; a fault poll | up to **2.8 GiB** (wholly-zero 2 MiB chunks; 3.5 GiB by 4 KiB pages) [M, section 39]; real gain unknown until the writers are known | high: one missed writer is a lost write and possibly F53's freeze. Section 48: a by-value search still misses one write per run | E1 below, then: name the writer of the one remaining hit (run 21 at 34 s) from a dumped buffer |
| C | **Pin only what the GPU can reach; CPU heaps stay ordinary memory** — the heaps no GPU work names (`AssetHeap`, `Wwise`, `Physics`: 1.6 GiB) are not imported; a read-only zero or PRT mapping covers them so a stray GPU read is a zero, not a fault | the import policy (per heap, from a list measured on the title, not from the protection bits) | 0 resident at once; **up to 1.6 GiB becomes swappable** (zram holds it at about 4:1, section 16) | medium: section 39 refuted the same idea for three other heaps; these three had no find in 140,000 buffers, which is absence of evidence | a run with `BC5_GUARD_NOGPU_SCAN=1` restricted to these three heaps over his whole route; zero finds over a long play is the gate |
| D | **Their model: translate and copy** — recompile native shaders, resolve every pointer on the CPU, GPU-owned buffers and textures, dirty tracking, read-backs | the whole direct path: this is RPCSX's or shadPS4's design, not a change to ours | the wall is gone (guest RAM swappable; GPU holds what it uses) | the project's premise (native command streams and shaders, no translation) is given up; speed drops to theirs; years of their work | none proposed |
| D′ | **Hybrid: direct for hot heaps, copies for cold** | — | — | **not coherent**: a native shader can address any heap, so a "cold, copied" heap needs translation of the shaders that reach it; without translation it is option C | — |
| E | **userptr instead of udmabuf** (pages not pinned) | the import path | 0: every listed BO is re-faulted per submission, and 12 GiB cost about 60 ms per submission (F38's 5 ms/GiB) | — | none; rejected again, now with the kernel's reason |
| F | **GPU-owned BOs mapped into the guest** | the memory backend | 0 for the wall (less reclaimable); possible speed from 2 MiB pages | — | none for memory |
| G | **Fault-tracked residency** (bind what the GPU used lately, re-bind on demand) | — | — | the GPU cannot wait for a page; a miss is F53's freeze. Needs complete discovery, which only translation gives | none |

## 6. Recommendation

1. **Keep the direct architecture.** The wall is not caused by sharing memory with the GPU as such: the console
   does the same and holds the same 12 GiB. A rebuild to the copy model (D) would remove the wall by removing the
   project.
2. **Do A now.** It is the only option whose saving (0.7–1.1 GiB) exceeds the measured deficit (0.4–0.5 GiB) at low
   risk, and none of it is a workaround: it is the part of the console's memory layout we do not reproduce.
3. **Prepare B behind E1.** It is the only large lever inside the guest's memory (2.8 GiB), and it is "our defect"
   in the strict sense: udmabuf creates those pages. But it is sound only with exact write-target tracking, and the
   last zero-skip series shows one writer we cannot name yet. No build before E1 and the writer are known.
4. **C after its gate.** Cheap to build (a list), but the gain is swappability, and the gate is a long clean scan.
5. Not proposed: D, D′, E, F, G.

With 0415 (agreed tonight): it owns the lock side (imports prepared outside the device mutex, `wait_jobs`); this
experiment owns what is imported and when it is given back. Its measurement: in the menu load the mutex is held
9–12 s of 16–21 s, imports are 1.1 s of that.

## 7. The first experiment (E1): what does the GPU do at a page without backing? (box, about 15 minutes, no game)

Question: on gfx1013 with kernel 7.2, for one GPU job (the existing `dispatch-min` buffer-fill and buffer-read
shaders, GFX ring):
1. a read from a PRT-mapped page: the value read, any kernel line, the job's time;
2. a write to a PRT-mapped page: any kernel line, the job's time, whether later jobs run;
3. a read from a page mapped read-only onto a zero BO: the value;
4. a write to that read-only page: the kernel line, what `AMDGPU_INFO_GPUVM_FAULT` returns (address, status), the
   job's time, whether the ring needs a reset, whether the zero BO stayed zero.

What it decides: if 1 and 3 read zero silently and 4 is a cheap, named fault with the BO intact, option B has a
sound floor (a missed writer is detected with its address and costs one dropped write, never garbage in another
page) and C's cover mapping is safe. If 4 is F53's freeze, B needs complete write-target tracking with no net, and
its risk stays high. Needs `--submit` (hard rule 5): the maintainer's or the top session's slot, a saved desktop,
the kernel log streamed.

Second, without the GPU: the `fdinfo` breakdown of section 16's 583 MiB and of the VRAM (option A), one run.

## 8. After E1 (2026-11-13; README section 55)

E1 ran: on gfx1013 a shader's read of a PRT page and of a page mapped readable only gives zeros with no fault; a write
to a PRT page vanishes without a sign; a write to a read-only page is a named page fault (address and status readable
through `AMDGPU_INFO_GPUVM_FAULT`), the job never completes, the kernel's timeout comes 2.03 s after the fault and
the ring reset succeeds at once; the page is intact and a new context on the same device works. One sample each, no
title running.

### 8.1 What changes in the options

- **Option B has its sound floor.** A never-written chunk under a view is mapped **read-only onto one zero BO**: no
  udmabuf, no pinned page. Reads are right (the file holds zeros there). A GPU write is a named fault with its
  address; the host then imports that chunk for real and goes on. A missed writer is detected, never silently lost,
  and nothing is aliased (nothing can be written into the shared zero page). This is the learned windows' loop with
  nothing remembered between runs and nothing pinned in advance.
- **PRT must not be that cover.** A PRT write vanishes without a sign, so PRT under anything the title mapped
  repeats the zero skip's defect (section 48). This settles R2 of `DESIGN-learned-windows.md`: a PRT background is
  right only over addresses the title did not map (the console drops writes there, if F257 holds beyond the AMM
  window); under a view that is not imported the cover is the read-only zero mapping. The switch `BC5_GUARD_PRT_BG`
  as built (a PRT span under everything, real mappings replacing it) is safe only while every view is imported
  whole, which the box cannot afford (section 53).
- **Option C's cover** (CPU-purpose heaps out of the pin) gets the same net: read-only real pages instead of zero
  pages are not possible (they would have to be pinned), so C stays "unmapped for the GPU, a fault names the miss".

### 8.2 The next question: what a recovered fault costs in a real frame

E1's faulting job was ours and nothing depended on it. In the title the lost job is a frame's work: labels it
should have written are never written, later jobs wait on its results, and the title may wait for ever on a fence
the reset cancelled. Today's recovery (a device reopen after 12 s) has brought the title back after learned faults
before (F44, F53), so it is not hopeless, but what state the frame is in afterwards has not been looked at.

**The smallest experiment (E2), not built:** a default-off test switch in a private build,
`BC5_GUARD_RO_FLIP=<seconds after the first flip>`: once, at that time, the GPU mapping of ONE imported 2 MiB chunk
of a GPU-written eager heap (the newest render-target hint) is replaced by a mapping of the **same pages, readable
only**. The data stays where it is; the GPU's next write there faults by name. The existing recovery runs, the
mapping goes back to read-write, and the run goes on. Recorded: the kernel lines, the stall from the fault to the
next flip, whether the title continues and for how long, the journal's label and wait lines around it, and the
picture as he sees it. Runs: the scripted route, the flip in the menu (little at stake) and then in play. Risk: the
ring reset under the title's load is the one that failed in F260 and sections 38 and 53; a failed reset reboots
the box. It needs its own slot and the standing stop rule.

### 8.3 Fault handling in 2 s instead of 14 s

[C] `recover_after_timeout` sleeps 12 s ("the kernel's timeout + reset") after our own 2 s fence timeout, then opens
a fresh device and rebuilds every import and mapping. [M, one sample] On this kernel the ring's own timeout fired
2.03 s after the fault and the reset was complete 0.1 ms later; a new context on the SAME device then ran jobs with
all mappings in place. So of today's 14 s, about 10 s is a sleep written for an older kernel's 10 s timeout
(TODO(verify): the kernel's gfx timeout value on the box; it is a module parameter and is not ours to change).
What a 2 s path takes:
1. wait for the kernel instead of sleeping: poll `amdgpu_cs_query_reset_state` (or the hung fence's status) until the
   context reports the reset, with the 12 s as the upper bound, not the wait;
2. keep the device: make a new context and re-create what belongs to a context (the state stack, the GDS/OA/GWS
   options) instead of `Device::open`; the imports and the 20,000 mappings stay, which also removes the re-import
   (2 s of the 14, F44);
3. read `AMDGPU_INFO_GPUVM_FAULT` at once (the catcher already does) and act on the address before the next
   submission: import the chunk (option B), or journal it (the catcher);
4. the lost job: re-submit it once after the fix when the fault was ours to cure (a read-only cover we placed),
   which is what makes B's net cheap in a frame; whether that is sound is E2's question.
Each of these is a change to the shared direct path's recovery and needs its own switch and a test that injects a
fault (E2's flip is that test).
