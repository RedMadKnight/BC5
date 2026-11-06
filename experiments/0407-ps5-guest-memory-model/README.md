# 0407 — how the PS5 manages guest memory, and what our host should change

> **Superseded by 0408** (branch `exp/0408-memory-review`; decided 2026-11-06). The rebuild follows 0408's
> recommendations. **Dropped:** Z2 (zero skip v2), R1 (release punch), and coding L1 before the empty-learned-file arm.
> **Carried into 0408:** P1 (census) and N1 (null BO), which are implemented in e10. Nothing below was built or run.

**Question.** The maintainer named four host memory mechanisms as suspects: one pinned memfd shared through udmabuf,
eager import of whole GPU heaps, the high-bit alias mapping, and learned fault windows. For each one: what does the
real console do, and what do other emulators and the Linux stack offer? Which change makes our host behave like the
console, with the biggest RAM gain at the lowest risk?

**Setup.** Laptop only, research, 2026-11-06. There was no box access: no GO was asked for, and nothing ran on the
box.
- *Host code:* main 029e0d6b.
  - `P:` is a line of `backend/kytyplus-patches/0001-bc5-lle-agc.patch`.
  - `D:` is a line of `backend/src/direct.cpp`.
- *Our records:*
  - `docs/HANDOFF.md` (F-numbers);
  - experiments 0017, 0023, 0042, 0056, 0066, 0102, 0156, 0288, 0330, 0333, 0379 and 0401 (series e and e7);
  - exp 0406's memory audit (`audit0406-memory.md` in the top session's notes folder).
- *Other emulators.* Read from the local clones in `Downloads/bc5/refs/`, which are public GPL repos, and
  cross-checked on GitHub by two research agents:
  - shadPS4 60c42b9 (web: 34a1d4dd);
  - AnyPS5 (boykopovar) 27c88a8;
  - KytyPS5 at 09753bf (web: 182161eb);
  - obliteration 2a53d5c;
  - RPCSX e8ae148;
  - Mesa ab2374a (web: e6dd90e0);
  - Linux master f66469d9 (web).
- *Provenance.* Public sources only: press interviews, a public Epic forum post, open-source emulator code, kernel
  and Mesa source. No SDK material, no firmware, nothing from disassembly. One search hit that looked SDK-derived (a
  console-port `user_malloc.cpp`) was skipped unopened. **Inferred** marks every step that is reasoning rather than a
  source.
- *Number claim.* Only the repo side is claimed (this directory, branch `exp/0407-ps5-memory-model`). `~/bc5-work/exp0407`
  on the box is **not** created yet, because there was no box GO. The top session should create it, or hand the
  claim over, when it grants the box slot.

## Result

### 0. What the console does, in one paragraph

- **Sizes.** A PS5 title gets a fixed budget of about 12.5 GB. That figure comes from press reporting, not from Sony
  ([TweakTown](https://www.tweaktown.com/news/97009/playstation-5-pro-new-pssr-to-radically-improve-image-quality-has-1-2gb-more-ram-for-games/index.html)).
  KytyPS5 models it as `GUEST_MEMORY_BUDGET` = 12,800 MiB, minus a 64 MiB cache, minus page-table memory past 64 MiB
  each for the CPU, GPU and AMM tables (KytyPS5 09753bf `src/kernel/memory.cpp:68-70`, and the 09753bf diff).
  - The table sizes are a title setting. Epic tells UE titles to raise `CpuPageTableSize`/`GpuPageTableSize` from 64
    to 96 MB ([Epic forum](https://forums.unrealengine.com/t/can-we-get-details-on-the-ps5-large-memory-pages-support/2615328)).
- **The two kinds of memory.** Sony's own PS4 description: in direct memory "the game controls all aspects of its
  allocation". Flexible memory is managed by the OS but is "100 per cent the game's memory"
  ([Game Informer, 2013](https://gameinformer.com/b/news/archive/2013/07/29/sony-addresses-ps4-ram-report)).
- **Protection bits.** Mappings carry GPU protection bits beside the CPU ones: `GPU_READ` 0x10 and `GPU_WRITE` 0x20
  (shadPS4 `src/core/libraries/kernel/memory.h:40-41`; KytyPS5 uses the same bits).
- **Address space.** Every emulator gives the GPU the CPU's addresses, and so do we (inferred for the hardware; no
  Sony statement).
- **AMM.** The AMM window sits at 0x0800_0000_0000, 512 GiB (KytyPS5 09753bf `src/kernel/memory.h:45`). It is mapped
  and unmapped by title command buffers in 16 KiB pages (KytyPS5 `src/libs/libAmpr.cpp`).
- **What no public source covers.** No public source says whether pages are committed at allocation, whether game
  memory is ever paged out, or what released memory does on the hardware.
  - Every emulator commits eagerly (shadPS4 `PoolCommit` → `impl.Map`) and returns released ranges to a free list
    (shadPS4 `Free()`, KytyPS5 `AddFreeRange`).
  - **Inferred:** the console keeps the title's memory resident and never swaps it.
- **What that means for us.**
  - **Pinning itself is console-like.** The console's ~12.5 GB sits beside a separate OS reserve.
  - On our 15.2 GB box, Linux, Plasma, the emulator, bc5-mount and the page cache must all fit in what the title
    leaves. With 11.4 GB pinned, that is ~1 GB (F353).
  - The host differs from the console in two ways that cost RAM. It **materialises memory the title only reserved**
    (all-zero chunks: 3.4–3.7 GB, F394). It also **keeps memory the title released** (no punch, P:25011).
  - On the console, untouched pages cost nothing, because no other process wants them (inferred).

### 1. Guest memory as one memfd shared through udmabuf dma-bufs (exp 0017, 0023, ADR 0006)

- **The console.** Direct memory is a physical range the title allocates and then maps. The GPU sees it at the same
  VA (§0). There is no OS swap of game memory (inferred, no source), so being resident is normal there.
- **Other emulators.**
  - *Same backing as ours.*
    - shadPS4: one `memfd_create("BackingDmem")` (`src/core/address_space.cpp:751`).
    - KytyPS5 and upstream KytyPlus: `memfd_create("KytyDirectMemory")`.
    - AnyPS5: `memfd_create("direct memory")`, 13,824 MiB, sealed (`core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:294`,
      `DirectMemory.hpp:10`).
    - None of them punches holes on release. AnyPS5 zeroes reused pages instead (`ZeroReusedPhysical`, `DirectMemory.cpp:308`).
  - *How the GPU sees it differs.*
    - shadPS4, KytyPS5 and RPCSX **copy** guest bytes into device-local Vulkan buffers. shadPS4 tracks CPU writes with
      userfaultfd write-protect (`src/video_core/page_manager.cpp:290`) and uses sparse arenas.
    - AnyPS5 **imports** the memfd through udmabuf, like us (`libSceAgcDriver/Graphics/src/GuestBufferMemory.cpp:582-618`):
      - in 64 MiB chunks (`ImportChunkBytes`, :624);
      - refcounted per guest buffer (`weak_ptr` in `ImportChunks`, :641-655), so a chunk is unpinned when no buffer
        uses it any more;
      - large buffers become sparse Vulkan buffers bound over the chunks (`vkQueueBindSparse`, :847).
- **Linux.**
  - *udmabuf.* `memfd_pin_folios` allocates any missing folio and pins it at creation. The pin is "effectively the
    same as using FOLL_LONGTERM", and only `release_udmabuf` unpins (Linux `drivers/dma-buf/udmabuf.c:316`,
    `mm/gup.c:3450-3466`).
  - *No unpinned alternative.* udmabuf has no dynamic-exporter callbacks, and no unpinned udmabuf or shmem dynamic
    exporter exists upstream.
  - *So creating an import materialises every zero page.* That is the mechanism behind F394.
  - *userptr* (`amdgpu_hmm.c`) does not long-term pin, but it walks HMM for each listed BO on every CS (`amdgpu_cs.c`).
    On our box, writable userptr over the memfd failed (F24), and the per-submit walk is what ADR 0006 removed (F38,
    F54).
  - *KFD SVM* gives fault-driven, unpinned GPU mappings. Eviction quiesces only KFD queues, though, not graphics
    jobs (`kfd_svm.c`), and gfx1013 support is unknown. Not usable for us (inferred).
- **Our host.**
  - The direct memfd is sealed against shrinking (P:24897, P:24905).
  - The private memfd is 1 TiB, sparse, with offset = guest address (P:24962-24979).
  - The import unit is a 2 MiB chunk (P:28698), via `UDMABUF_CREATE` + `amdgpu_bo_import` (D:826-863).
  - The import loop: P:28990-29030.
  - Nothing is released except by a merge or a reopen (exp 0333 "Known before").
  - Re-committed private memory is zeroed with `memset` over its data runs (P:25008-25025).
- **The gap.** The backing is the same as every emulator's. Our difference from AnyPS5 is that our imports are
  never dropped: AnyPS5 frees a chunk when its last buffer goes. Our difference from the console is that the console
  "pays" for reserved-but-untouched memory with RAM that nothing else wants, and we pay with RAM that Linux needs.
- **Change R1, release on free.**
  - When the title releases direct memory, or unmaps flexible memory: punch (`FALLOC_FL_PUNCH_HOLE`) the 2 MiB chunks
    that no BO covers.
  - For chunks inside a BO: free the BO when every chunk in it is released (GPU drained first, as the merge already
    does), then punch.
  - Console analogue: released memory returns to the free pool (emulators, §0).
  - *Gain:* ≤ 0.35 GiB (exp 0288 Q2: shmem was 74–350 MiB above pinned + private).
  - *Risk:* low for unimported chunks. Medium for imported ones: a stale GPU mapping after the free means a fault, so
    unmap first.
  - *Effort:* M.

### 2. Eager import of whole GPU heaps in large runs (exp 0042, 0066, F125; exp 0333's "Known before")

- **The console.** A GPU page-table entry exists for every mapping the title made with GPU bits. Those pages are
  real memory whether or not anything has written them (inferred from §0). The console has no eager/lazy
  distinction: "mapped with GPU bits" is the whole rule.
- **Other emulators.**
  - The copying emulators upload on demand: what a draw or dispatch binds, plus tracked CPU writes. The GPU sees only
    what was uploaded.
  - AnyPS5 imports per registered guest buffer. Nobody imports a heap "in full" by name.
- **Linux.**
  - BO size does not change RAM: pinning is per page. Large BOs only cut the per-CS BO-list cost (F125: 1.5 → 1.0 ms
    a frame).
  - Imported dma-buf BOs cannot be `VM_ALWAYS_VALID`, which only GEM_CREATE BOs can be (`amdgpu_vm.c`,
    `radv_amdgpu_bo.c` ~611). So the BO list stays.
  - The cost of large BOs: a 1 GiB BO cannot be partly unpinned. Releasing any chunk means splitting the BO, which
    the zero skip did: +28 BOs, F542.
- **Our host.**
  - Name lists: lazy at P:28757, eager at P:28783.
  - The eager loop imports every chunk of the view (P:28990).
  - `kDMaxBo` = udmabuf's `size_limit_mb`, clamped to 1,024 (P:28700-28710).
  - The merge pass has a 256 MiB budget and 512 remaps (P:29047).
  - The eager list is 10,047 MiB, 90 % of what is pinned (F353). 2.8 GB of the two render heaps is all zero (F394,
    F402).
- **The gap.** Pinning the GPU heaps matches the console, which has them physically. The excess is the zero part.
  The console needs no RAM it lacks for that part; we do.
  - Our GPU cannot fault and retry on graphics queues (exp 0333; F88: a fault is a 14-s freeze). So the only way to
    leave zero chunks out is the exp 0379 skip: a stand-in mapping plus a watcher.
  - That watcher's take-backs were associated with F403 hangs, and lost GPU writes are possible until it sees them
    (F542, ≤ ~2.75 s).
- **New constraint from Mesa.** The stand-in must **not** be PRT.
  - On GFX10–12, "SMEM loads on a NULL PRT page throws a VM fault and hangs the GPU" (Mesa
    `src/amd/common/ac_gpu_info.c:437-442`, `has_smem_with_null_prt_bug`).
  - For that reason RADV backs unbound sparse ranges with a zeroed BO instead of PRT (`radv_amdgpu_bo.c:144-181`,
    `bind_low_null_prt`).
  - Our scratch BO and the zero skip's canary BO are already this workaround.
- **Change Z2, zero skip v2.**
  - Keep exp 0379's skip with per-run canary BOs, not PRT.
  - Three changes from it:
    - (a) take-backs (hint, CPU write or canary hit) are queued and applied only at a drained submission boundary,
      never as a remap under a running job;
    - (b) a chunk joins the skip only after it is zero in N ≥ 3 consecutive mapped scans, and lies outside the hint
      and learned windows;
    - (c) a run with a canary hit leaves the list for good.
  - *Gain:* 0.4–1.9 GB of GTT. r7m measured −440 MiB GTT and −739 MiB swap, and the bench F541 −1.9 GB.
  - *Risk:* medium–high. It is the F403 association, and (a) is a guess at its mechanism, not a proven fix.
  - *Effort:* M.
- **Change P1, a census of the GPU protection bits (log only).**
  - At each layout change, journal per view: name, guest protection (CPU/GPU bits as the title gave them, before
    `KYTY_BC5_ALL_RW` widens them), eager/lazy/data and bytes imported.
  - It decides whether "import iff GPU bits", the console's own rule, can replace the name lists and the learned
    windows.
  - *Gain:* none now. It is the basis for removing heuristics.
  - *Risk:* none.
  - *Effort:* S. It needs the title's protection kept per view; check whether KytyPlus still has it.

### 3. Guest memory mapped again under high address bits (exp 0056, F92, F110, F112)

- **The console.** No public source explains why the title's function pointers carry 0x80 in bits 47:40, nor
  describes any aliased or tagged mapping of the same memory (agent search: none).
  - That value is bit 47, the top of a 48-bit VA. Exp 0056 found it on program pointers in constant buffers. It is
    consistent with a PS5 GPU that ignores those bits or maps code there too (exp 0056, TODO(verify) there).
- **Other emulators.** None of the local clones maps such an alias. The copying emulators never hand the GPU a raw
  guest pointer for code (inferred).
- **Linux.** The alias is a second GPU VA mapping of the **same BOs** (`map_alias`, D:911-936; sign-extended above
  2^47 for the kernel's VA hole). It costs page-table entries, not pages.
- **Our host.**
  - `aliases_apply` maps (byte << 40) + address (P:29500-29514) at most once a second.
  - `alias_learn` refuses faults whose low 40 bits name no guest memory (P:29518-29545).
  - The 0401 runs log "5 windows, 192.0 MiB mapped again" (61 lines in `0401*/raw/`).
- **The gap.** RAM gain 0. The cost is ~192 MiB of extra GPU VA, i.e. at most ~0.4 MiB of 4 KiB PTEs (inferred:
  8 bytes a 4 KiB page), plus one unmap/map pass per mapping change.
- **Change: none for RAM.** Keep it, because without it the title's program fetches fault (F110). Not in the test
  build.

### 4. Learned windows (exp 0156–0160, F203, F208, exp 0288)

- **The console.** It has nothing like this. A GPU access is either inside a GPU-mapped page or a real fault.
  Learned windows exist only because we do not import by the title's own GPU mappings (inferred, see P1).
- **Other emulators.** None of them learns windows from faults.
  - shadPS4 has a GPU fault buffer drained by its `FaultManager`, which uploads the faulting block (its
    `buffer_cache.cpp`; BDA page table). That is fault-driven at block grain, made possible because its GPU reads go
    through a BDA table it controls (inferred: we run the title's own shader code, so we cannot interpose).
- **Our host.**
  - `learned_add`: a 96 MiB window from 32 MiB below the fault's 64 MiB block (P:29546-29548).
  - `map_window` → `direct_force` forces those chunks into the import (P:29213, P:29694+).
  - `scratch_fill` maps one 2 MiB zero BO into the holes. That is no RAM: 1,975 maps, 8,096 MiB of VA (exp 0288).
  - `learned_apply` runs at every layout-generation change, from the submit path (P:33845).
  - The file holds 107 windows, 46 of them at junk addresses that import nothing. The 61 real ones asked 3,884 MiB
    in the first minute (exp 0288).
  - `learned_apply` ran 10,028 times: 83 s of a 1,742-s session, at most 633 ms, on the game thread (exp 0288).
  - In the two render heaps, 932 + 946 MiB of zero chunks lie inside learned windows (F402). The heaps are eager
    anyway, so that costs no extra RAM, but it blocks the zero skip there.
- **The gap.** There are two costs.
  - *RAM:* forced chunks outside the eager heaps, ≤ 0.7 GB (the exp 0379 notes' estimate).
  - *CPU and stalls:* the sort and copy of the whole mapping list at each change, up to 633 ms.
- **Change L1, a learned-window trim.**
  - Mode 1:
    - drop entries whose address is ≥ 2^47 or whose low 40 bits name no guest view;
    - skip every chunk of a window that lies inside an eager view, since it is imported already;
    - cache the per-window hole list between generations.
  - Mode 2: mode 1, plus clip each window to the guest views it overlaps. New faults learn the faulting 2 MiB chunk
    ±1 chunk instead of 96 MiB.
  - *Gain:* up to ~0.7 GB of RAM (mode 2, inferred), most of the 83 s of game-thread time, and the 633-ms stalls.
  - *Risk:* low. A chunk that was really needed faults once and is learned again, which is a 14-s freeze. The old
    file stays the fallback.
  - *Effort:* S.

### 5. Found on the way: `BC5_DIRECT_AMM_PRT` maps NULL PRT pages on a GFX10 GPU

- `map_prt_window` maps the AMM window 0x8000000000 + 64 GiB as `AMDGPU_VM_PAGE_PRT` (P:28631, D:886-896). It is
  mapped again after each reopen (P:32769).
- Mesa's caveat in §2 says an SMEM load from such a page faults and hangs the GPU on GFX10. RADV avoids it with a
  zeroed BO.
- Exp 0406 lists this switch as on ("keep", item 5). Whether the maintainer's shortcut sets it today is not on the
  laptop: TODO(verify) in `bc5-run.env`.
- F403 records "no page fault", so this is **not** shown to be F403's cause. It is a hang hazard the console does
  not have.
- **Change N1, a null BO.** Under the AMM window, map one shared zeroed BO read-only (without `AMDGPU_VM_PAGE_WRITEABLE`)
  instead of PRT, as RADV's `null_prt_bug` BO does.
  - What a GPU write to a non-writable page does on gfx1013 with retry off (dropped plus a fault line, or a hang) is
    TODO(verify). So N1 has its own arm.
  - *Gain:* 0 RAM. 64 GiB of VA over a 2 MiB BO costs page tables only.
  - *Effort:* S.

### 6. Outside the four, for the record

- **AMM pool borrowing.** On top of the title's pool, the host borrows direct memory for AMM maps (P:38829-38845).
  With `KYTY_BC5_MEMORY_FROM_PARAM=1` the pool ran dry ("map of 0x4000000 refused", exp 0401 e2 18:14).
  - The console has no borrow path in KytyPS5's model (inferred): the title gives the pool (`AmmGiveDirectMemory`).
  - This belongs to the water session's AMM-pool fix, not here.
- **The budget switch.** Measured, `FROM_PARAM` lowered pinned memory by only ~120 MiB (exp 0401 e2), because the
  pinned heaps did not shrink with it.
- **The page cache and the mount.**
  - The console's APR reads go straight into title memory (KytyPS5 `AprCommandBufferReadFile`), with no OS page
    cache.
  - Ours go through FUSE and the disk cache, and can sit in the page cache twice (exp 0406 item 18).
  - The frame rate follows those re-reads (F620: 41.2 against 24.9 flips/s). This is the closest *non-pinning* gap
    to the console. It is a bc5-mount experiment, not part of this build.

## Ranked plan (RAM gain against risk)

| Rank | Change | Switch (default off) | RAM gain | Other gain | Risk | Effort |
|---|---|---|---|---|---|---|
| 1 | L1 learned-window trim | `BC5_0407_LEARNED_TRIM=1\|2` | ≤ 0.7 GB (mode 2, inferred) | game thread: most of 83 s per 29 min; stalls ≤ 633 ms | low (a re-learned fault = one 14-s freeze) | S |
| 2 | R1 release on free (punch + free a fully released BO) | `BC5_0407_RELEASE_PUNCH=1` | ≤ 0.35 GiB | console-like release | low (unimported) / medium (imported) | M |
| 3 | P1 GPU-protection census | `BC5_0407_PROT_CENSUS=1` | 0 (decides whether "import iff GPU bits" can replace the name lists) | — | none (log only) | S |
| 4 | Z2 zero skip v2 (drained take-backs, N ≥ 3 scans, no PRT) | `BC5_0407_ZERO_V2=1` + exp 0379's `BC5_DIRECT_ZERO_SKIP` list | 0.4–1.9 GB GTT | less swap and PSI (r7m: swap −739 MiB) | medium–high (F403 association, lost GPU writes) | M |
| 5 | N1 null BO instead of NULL PRT in the AMM window | `BC5_0407_AMM_NULL_BO=1` (with `BC5_DIRECT_AMM_PRT=1`) | 0 | removes a GFX10 hang hazard (Mesa) | low–medium (write behaviour TODO(verify)) | S |
| — | Aliases (mechanism 3) | none | 0 | — | — | keep |
| — | `kDMaxBo` / large runs (mechanism 2's BO size) | none | 0 | the BO-list cost stays as F125 measured | — | keep |
| — | Not adopted: userptr (F24; a per-CS HMM walk), KFD SVM (no graphics eviction; gfx1013 unknown), copying into device buffers like shadPS4/KytyPS5 (holds GPU-visible data twice and undoes ADR 0006), unpinned udmabuf (does not exist upstream) | | | | | |

## Proposed test build (fixes first, then one test)

- **One private build** on the objects of whatever binary is in his shortcut when the slot is given. The water
  session's AMM-pool fix and `FROM_PARAM` state are taken **as they are** and kept the same in every arm.
- **One unit:** `bc5LleAgc.cpp` for L1, P1, Z2 and N1, and `memory.cpp`/`memoryAddressSpace.inc` for R1, through a
  `mk0407.py` edit script in the 0401 style.
- **Switches.** Each switch is read once with `getenv`. Unset or `0` gives today's path, with one journal line per
  switch: `exp 0407: <name> on|off`.
- **New journal lines.**
  - `learned trim (exp 0407): N windows kept, J junk dropped, C chunks skipped in eager views, apply max X ms`
    every 60 s.
  - `release punch (exp 0407): P MiB punched, B BOs freed` every 60 s.
  - `prot census (exp 0407): …` once at G and once at the end.
  - `zero v2 (exp 0407): skipped S MiB, queued Q take-backs, applied A at drained boundaries, canary hits H`.
- **CPU tests before the box** (`test0407.cpp`, laptop stand-ins plus the box gate, R32 style):
  - window trim on a synthetic view list: junk, eager overlap, clip;
  - punch only over uncovered chunks (on a memfd: `SEEK_DATA` before/after);
  - the take-back queue drains only at the boundary hook;
  - every switch gives the same behaviour off and unset.
- **No GPU submission in tests** (hard rule 5).

## A/B arm plan (his slot-4 save, as exp 0401 r6c/r7m)

- **Runner.** exp 0401's `run0401t.sh MODE=route`: the save-slot list route (cross, down ×3, cross, cross), slot 4's
  Continue, standing still to G+900. RT on (memory: since 2026-10-28), JobArenaFix as in his shortcut.
- **Saves.** A named snapshot of his saves, with the private copy reset from it before each arm (coordination
  README; R45: no live gate).
- **Samplers.** exp 0330's `sample0330.sh` memory sampler plus the freeze watcher. The kernel log is streamed to the
  laptop.
- **Before each arm:** `drop_caches`, which the sudoers list allows, so every arm starts cold like exp 0379's.
- **Order, ABBA so that run order and warm-up cancel** (exp 0406 found r6c/r7m confounded by order):

  | Arm | Switches added to his shortcut's words |
  |---|---|
  | a1 | none (control) |
  | b1 | `BC5_0407_LEARNED_TRIM=2 BC5_0407_PROT_CENSUS=1` |
  | c1 | b1 + `BC5_0407_RELEASE_PUNCH=1` |
  | d1 | c1 + `BC5_0407_ZERO_V2=1` + exp 0379's zero list |
  | d2, c2, b2, a2 | the same, in reverse |
  | n1 (only if `BC5_DIRECT_AMM_PRT=1` is in his words) | a1 + `BC5_0407_AMM_NULL_BO=1` |

- **Length.** About 19 minutes an arm, 8 (or 9) arms, about 2.6–2.9 h of box time. The box claim and the
  `~/bc5-work/exp0407` claim come from the top session.
- **Measures per arm,** all from the memory lines plus the journal:
  - MemAvailable floor and median;
  - GTT used, max;
  - swap, max;
  - PSI mem "full": peak and cumulative stall over G..G+900;
  - flips/s **over G+120..G+900 only**, with the window taken on one clock and tested on a slow-menu/fast-play case
    (R11, Codex's 0401 note on `run0401t.sh:188-190`);
  - seconds with a gap over 100 ms, and the longest gap;
  - `learned_apply` total and max ms;
  - pinned BO count;
  - the exp 0407 counters.
- **Decision rule.** A change counts as a gain only if both arm pairs move the same way, by more than the e8 spread
  (3.1 flips/s, ~9 %), with ≥ 300 MiB on the MemAvailable floor or ≥ 500 MiB on GTT max.
- **Stops.** Any amdgpu ring timeout or reset line stops the chain. Every canary hit and every re-learned fault is
  counted and reported. A 14-s freeze in b or c means mode 2's clip was too tight: that arm pair reruns with
  `LEARNED_TRIM=1`.

## Verdict

**Open: research done, no test run.**
- The console keeps a title's memory resident (inferred; no public source either way). So pinning as such is not
  the bug.
- The RAM gap against the console comes from:
  - memory the title only reserved but our imports materialise (zero chunks, learned windows);
  - memory it released that we keep;
  - host-only costs: the page cache and the mount.
- The aliases and the BO size cost no RAM.
- Next: the build and arms above, once the top session gives a box GO and a slot.
- Separate from RAM: `BC5_DIRECT_AMM_PRT` maps NULL PRT pages that Mesa calls a GPU-hang hazard on GFX10. Check
  whether it is on in his words, and if so give it its arm (N1).
