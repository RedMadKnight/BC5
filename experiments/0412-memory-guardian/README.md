# 0412 — why the second title chokes on memory, and a guardian that keeps it inside a budget

**Question.** At the maintainer's current save the second title runs 12–18 fps with the box out of memory. Where do
the pinned 12 GiB go, what in the chain makes frames slow, and what component ("guardian", *strażnik*) would keep the
guest and the emulator each inside a fixed budget, as the console does?

**Setup.** Laptop only, analysis and design, 2026-11-10. **No box access**: no GO was asked for, nothing ran, nothing
was read on the box. Nothing is built.
- *Sources.* Worktrees `bc5-0401` (exp 0401 README, series e10/e11 and the 11-10 plays; exp 0288, 0330, 0379),
  `bc5-0407`, `bc5-0408` (§A, §C, §D, §G6), the notes folder's `audit0406-memory.md` and `0408-*.md`,
  `captures-20261109-hang/direct-slice.txt`, `docs/HANDOFF.md` (F-numbers), patch 0001 (`P:` = a line of
  `backend/kytyplus-patches/0001-bc5-lle-agc.patch` at 0401's tip).
- *Marks.* **[M]** measured, with its record. **[I]** inferred: reasoning from code or from other measurements.
  **[K]** kernel behaviour quoted from memory of the Linux source, not re-read for kernel 7.2.15: verify before
  relying on it.
- *Number claim.* Repo side only: this directory, branch `exp/0412-memory-guardian`, worktree `bc5-0412`, from main
  029e0d6b, uncommitted. 0410 shows nowhere on the laptop and 0411 is the water session's box directory, so 0412 was
  taken. **`~/bc5-work/exp0412` is not created**: the top session should create it, or say which number to use, when
  it gives a box slot.

## Result

### 1. Where the pinned memory goes

**The split in the slow area is not measured.** No per-heap table exists from his current save. The only per-heap
table is exp 0288's (10-25, RT off, an older save, 11,224 MiB imported). What is known about today's 12.05 GiB is the
total and how it differs from that table.

| Category | MiB | Source | Does the console hold it? |
|---|---|---|---|
| `RenderGpuWcLarge` (GPU heap, eager) | 2,758 | [M] exp 0288 | yes, but about half is untouched: 1,378–1,442 MiB all-zero ([M] F394, F402, F540) |
| `CommitIABufferAllocator` (GPU heap, eager) | 2,736 | [M] exp 0288 | yes; 1,376–1,384 MiB all-zero ([M] the same) |
| AMM pool (streaming pool, 16 KiB pages; 653 views + 18,661 small) | 3,130 | [M] exp 0288 | yes: the 3 GiB the title hands over (F206). Its zero share is not measured |
| `RenderGpuRwLarge`, `DynamicHeap`, `Physics`, 11 small eager heaps | 414 + 328 + 192 + 489 | [M] exp 0288 | yes |
| Non-eager heaps (`InitAllocator`, `AssetHeap`, `Wwise`, …): CPU-written data plus chunks forced by learned and hint windows | 1,178 | [M] exp 0288 | the data yes; the forced part only if the GPU maps it. How much is forced is not measured |
| Private memfd (eboot, libraries, stacks) | 262–276 | [M] exp 0288; 270 on 11-09 | yes |
| **Sum at the old save, RT off** | **11,416 + 276** | | |
| RT on | about +600 | [M] bench to bench, not an A/B (0408 §C4) | yes (the title's BVH and RT data live in its own heaps) |
| The newer slot-4 save against the older one | about +800 GTT | [M] 0408 §A, one binary | unknown which heap |
| The slow area today against the same area on 11-09 | +350 (11.7 → 12.05 GiB in 2 min; 8.4 → 12.0 after a reboot). 11-09 reached 12.0–12.3 only at minutes 28–36 | [M] 0401 README | unknown which heap. Per-heap lines may be in the four play journals on the box (`play-20261109-2203`, `play-20261110-1732`, `-1817`, `-1837`); not read, no GO |
| Scratch windows ("holes get a zero buffer") | 2 (one shared 2 MiB buffer; ~8 GiB of address space) | [M] exp 0288, P:29630 | no RAM here |
| Views and their GPU mappings (27,924 views, 27,945 mappings on 11-09) | < 10 | [M] count; size [I] | no RAM here |
| The high-bit alias (192 MiB mapped again) | 0 (page tables only) | [M] 0407 §3 | — |
| Host copies beside the guest: DMA snapshot ring 64, staging 96, tiler pool 96–128, RADV client 117 GTT | about 400 | [M] 0406, F628 | no: the console has no second copy [I] |
| Shader and pipeline caches | inside the emulator's 130–250 MiB of anonymous memory | [M] exp 0288 Q4 | — |

Outside the pinned memory, on the same RAM:

| What | MiB | Source |
|---|---|---|
| CPU-written guest pages that are not imported (the title's own CPU heaps, the lazy names) | 74–350 at a standing bench | [M] exp 0288 Q2 |
| zram's own store for what is swapped (1.4–1.7 GiB of swap) | about 400–600 | [I] at a 3:1 ratio; the real ratio is in `/sys/block/zram0/mm_stat`, not read |
| Page cache of the game's files (unpacked game, btrfs, 4 MiB read-ahead) | whatever is left; 580 at the bench (F541) | [M] |
| Desktop, journald, kernel | about 1,000 | [M] F353 ("~1 GB left with 11.4 GB pinned") |

**The arithmetic.** The box has 14.84 GiB for everything (MemTotal, read 11-10; §5). With 12.05 + 0.27 GiB pinned and
~0.4 GiB of host copies, about 2.1 GiB is left for Linux, the desktop, the emulator's own memory, the title's unimported CPU
heaps, the zram store and the page cache. [M] MemAvailable 170–750 MiB agrees.

**What the console would not hold, or holds once:**
1. *Nothing else competes for untouched pages.* The console's title budget (about 12.5 GB, press figure; KytyPS5
   models 12,800 MiB) sits beside a separate system reserve. Our zero chunks, 2.8–3.7 GiB [M], are pinned real pages
   that Linux then lacks. This is the largest difference.
2. *Released memory goes back to the pool.* We never unpin (P:25011, P:29179). [M] 74 MiB at a standing bench; across
   an area change it is **not measured**, and the pinned total only ever grows ([M] F623: steps of 39–119 MB with new
   areas).
3. *No page cache.* Game data is read once into the title's buffer [I]. We hold it in the page cache as well, and the
   4 MiB read-ahead pulls in data the title did not ask for.
4. *No compressed swap of game memory.* The console does not swap the title [I]. Here the only things that can be
   swapped are the small unpinned remainder, and swapping them costs RAM (zram) and CPU.
5. *A smaller pool on offer.* We offer 13,824 MiB of direct memory against the console's ~12,800. The title reserved
   12,162 at the old save [M]; what it reserves at the current save is not measured.

Not waste: views, scratch windows, aliases and PlayGo cost no RAM. `FROM_PARAM` is worth ~120 MiB [M].

### 2. The stutter chain

**Measured** (0401 README, the 11-10 plays; e10 and e11 alike):
- Frame 60–79 ms; GPU busy 15–26 ms; game thread 39–58 ms outside the host. After a reboot 75–204 ms.
- Pinned 12.05 GiB within 2 minutes; 650–940 "direct: N views" lines a minute; 220–390 "scratch: window" lines per
  2 minutes (twice the good-phase rate of 11-09).
- MemAvailable 170–750 MiB; PSI memory 4–73 %; ~40,000 minor faults/s; up to 7,800 major faults/s; swap-ins and
  swap-outs in the thousands of pages/s.
- When he walked into a new area: minor faults 11,000–23,000/s, PSI 0.2–3 %, 23–32 fps.
- The older slot-4 snapshot: 20 ms frames at 12.2 GiB pinned once the churn fell to ~200 views a minute.

**Inferred chain**, each link with what supports it:
1. **The GPU is not the limit.** [M] GPU busy is a third of the frame. The lost time is the game thread, outside the
   host's own code.
2. **Pinned pages stay on the kernel's reclaim lists.** [K] udmabuf pins the pages but does not mark the file
   unevictable, so reclaim keeps scanning them. For each one it removes the CPU page-table entry, then finds the page
   cannot be freed and keeps it. Support: [M] exp 0288 Q4, where the emulator's mapped memfd pages fell from 6.3 to
   1.7 GB while only 309 MiB was swapped; and [M] the 40,000 minor faults/s, which are the title touching those pages
   again. With 12.3 of 14.2 GiB unfreeable but still scanned, every reclaim pass walks a lot to free little, and a
   thread that allocates under pressure does that walk itself (PSI "some/full").
3. **The only swappable guest memory is the title's CPU heaps.** [I] `BC5_DIRECT_LAZY_NAMES` (`orbis_user_malloc`,
   `Wwise`, `SoundAlloc`, `FileSystem`, `UIStringAlloc`) and the unimported parts of the asset heaps are not pinned,
   so they are what the kernel pushes into zram. The game thread then waits on swap-ins. Support: [M] up to 6,500
   major faults/s in the emulator; disk reads cannot run at that rate on this NVMe, so they are zram swap-ins.
4. **zram feeds on the memory it frees.** [I] Each page swapped out leaves about a third of itself behind as
   compressed store, and compressing and decompressing run on the same CPU cores as the game.
5. **File reads are re-reads.** [M] F620, F689: frames follow the reads (r = −0.84 to −0.93). With no page cache left,
   every streamed asset comes from the NVMe again, and the 4 MiB read-ahead evicts more.
6. **Mapping churn runs on the game thread.** [M] exp 0288: `learned_apply` took 4.8 % of a session, up to 633 ms a
   call; it runs at every layout change (P:29694, P:33845), copying and sorting all ~28,000 mappings. Today's churn
   is twice that session's. That the churn causes the slow frames is a correlation, not shown.

**Why his current save and not the snapshot** is open (0401 README, "His first play on the e11 shortcut" onwards;
the top session's relay of 11-10).
- *Ruled out* [M]: e11's build and switches (e10 is as slow in the same place); the learned file (the same 66
  windows applied on 11-09 and 11-10); the box's state (a fresh boot was worse); the settings (identical lines in
  both play logs); a graphics option (his "Nie"); log volume (14 MB in 20 minutes).
- *Cannot be tested:* an older save. He has none from before 11-09 22:30.
- *What is left:* the game's state at his save. In this area it reaches 12.05 GiB pinned in 2 minutes; on 11-09
  the same area held 11.7 GiB and reached today's level only at minutes 28–36, just before the slowdown and the
  22:42 hang. So 11-09 ended in the same state that every play now starts in.
- *The level is a cliff, not a slope* [I]. The snapshot runs 20-ms frames at 12.2 GiB pinned, and his save runs
  60–79 ms at 12.05–12.3 GiB. Pinned size is the same; what differs is the churn (650–940 view lines a minute
  against ~200) and so how much unpinned memory the title needs at once. Once that no longer fits in what the pin
  leaves, links 2–6 feed each other. The box sits within a few hundred MiB of that point in both cases.
- *What would tell:* the ledger (candidate 1) at his save names the heap that holds the extra 0.35–0.8 GiB and
  whether it is orphans. The water session's offer, a play with RT off beside the sampler, is a fair cliff test:
  RT is worth about 600 MiB of pin ([M] bench to bench), so if the cliff reading is right he should run near the
  snapshot's frame rate there. RT off needs its reason stated (the standing rule); the reason is that the arm
  measures the cliff, not the build. It needs no build and it is the top session's and his decision.

### 3. The guardian

**The principle.** The console gives the title a fixed pool and keeps the system out of it. We cannot add RAM, so the
guardian does three things: it keeps a ledger of what is pinned and why; it refuses or returns memory before the
kernel has to thrash; and it tells the kernel which memory is the game's, so reclaim falls on caches first.

**Two budgets** (numbers are starting values, to be set from the ledger's first run):
- *Guest budget:* what the title is told it has. Today 13,824 MiB; the console's is ~12,800. Lowering it is blocked
  by the AMM pool fault at 12,800 (11-10, the 11-03 class; exp 0409's fix hit an int3). So the guest budget stays at
  13,824 until that is fixed. It is not in this build.
- *Emulator budget:* a ceiling on pinned bytes, `P_max` = RAM − host reserve. With a 2.6 GiB reserve that is about
  11,600 MiB. Everything below is about holding the pinned total under it, and about what happens when it cannot be
  held.

**Candidates.** All go into one test build, each behind its own default-off switch. Gain and risk are estimates
unless marked.

| # | Switch | What it does | Expected gain | Risk | Effort |
|---|---|---|---|---|---|
| 1 | `BC5_GUARD_LEDGER=1` | Log only. Every 10 s one line: pinned bytes by class (each eager heap, AMM, learned-forced, hint-forced, CPU data), counted at import, with no `SEEK_DATA` walk; **orphans** (pinned chunks no view covers); BOs, views, mappings; sync and `learned_apply` ms; emulator RSS, swap and faults; PSI. Extends e3's memory line | 0 by itself. It fills the "not measured" cells of §1 and sets `P_max` | none | S |
| 2 | `BC5_GUARD_MLOCK=pinned` | `mlock2(MLOCK_ONFAULT)` on the CPU view of every imported range, so the kernel moves those pages to its unevictable list. They are unfreeable already, so no memory is lost | Removes link 2: the scan of 12 GiB and the minor-fault storm. Possibly the largest gain in frames [I][K] | low. Needs `ulimit -l unlimited` in the launcher (and in the distrobox). An unlock is needed before an unmap or release | S |
| 3 | `BC5_GUARD_MLOCK=guest` | As 2, plus the title's CPU heaps (the lazy names and unimported data): the guest is never swapped, as on the console | Removes link 3: swap-ins on the game thread | medium: what is locked cannot be reclaimed, so if the rest does not fit the result is an OOM kill, not a slow game. Only together with 6 and 8 | S |
| 4 | Zero skip (`BC5_DIRECT_ZERO_SKIP`, built) | Does not pin all-zero chunks; a canary watches them | **[M] −500 MiB GTT, −750 MiB swap, PSI ten times lower** (0408 §A); −1.9 GB on the bench (F541) | the highest here: F403 hang, 3 in 19 arms against 0 in 10. His choice | 0 |
| 5 | `BC5_GUARD_ORPHANS=1` | Unpins a BO once no view covers any chunk of it and the GPU is drained (0408's R0). No BO split | Unknown until 1 reports the orphan count. If the +145 MiB/min growth in new areas is released-and-kept memory, this stops the growth | medium: a stale GPU mapping after the free is a 14-s fault; the unmap goes first | M |
| 6 | `BC5_GUARD_FILE=dontneed` (or `direct`) | After a large asset read lands in the guest's buffer, drop its page-cache copy (`POSIX_FADV_DONTNEED`); open asset files with `POSIX_FADV_RANDOM` so the 4 MiB read-ahead stops. `direct` = `O_DIRECT` reads | Frees the page cache's copy at once instead of by reclaim: less scanning, fewer evictions of the title's pages. Unmeasured | low for `dontneed`; a repeat read then goes to the NVMe (it does already under pressure). `direct` needs aligned buffers | S |
| 7 | `BC5_GUARD_APPLY=incremental` | `learned_apply` and `scratch_fill` only for windows that overlap the ranges that changed, with the sorted mapping list kept between calls | Up to ~5–10 % of the game thread and the 633-ms stalls ([M] 4.8 % in exp 0288; today's churn is double) | low to medium: a missed window is a GPU fault. A debug mode compares against the full pass | M |
| 8 | Launcher: cgroups | Emulator scope with `memory.swap.max=0` and `memory.low` = its unpinned working set; desktop and helpers under `memory.high`. No `MemoryMax` on the emulator: pinned pages are charged to it and a cap means an OOM kill | Reclaim falls on caches and the desktop first, not on the title | medium; **needs a box read first**: the emulator runs inside the distrobox container, so which cgroup it is in and whether the memory controller is delegated is unknown | S, no build |
| 9 | Launcher: kernel settings | `vm.watermark_scale_factor` up, so the background reclaimer starts earlier and the game thread reclaims less; `vm.page-cluster=0` (no swap read-ahead on zram); swappiness set after 3 | Smaller stalls; unmeasured | low, but these are system settings: the maintainer applies them himself, or approves a launcher that sets and restores them | 0 |
| 10 | `BC5_GUARD_PSI=<some %>` | The pressure loop. A thread reads `/proc/pressure/memory` each second. Above the threshold, in this order: (a) drop the journal's and asset files' page cache; (b) free orphans (5); (c) shrink host caches (staging 96 → 48, snapshot ring 64 → 32); (d) refuse new learned windows wider than one chunk ± 8 MiB; (e) log one "over budget" line with the ledger. It never kills and never unpins a mapped chunk | Turns "the kernel thrashes" into ordered trimming. Its worth depends on 5 and 6 | low for a, c, e; as 5 for b; as 0408 §G6 row 8 for d | M |
| 11 | `BC5_GUARD_PIN_CAP=<MiB>` | Admission. When the pinned total would pass `P_max`: do 10's steps first; if still over, import only the chunks with data in *non-GPU-write* views, and log. GPU-written eager heaps are always admitted | Holds the ceiling where it can be held | medium: a chunk left out that the GPU reads is a 14-s fault and a learned window. Off until the ledger shows which class grows | M |

**Not proposed:** an LRU that evicts mapped imports (a miss is a 14-s GPU fault; 0408 rejected it); a smaller
`KYTY_GUEST_MEMORY_MB` (crashes today); `MemoryMax` on the emulator (OOM kill); disk swap in place of zram for the
game (14–320 MiB/s small reads on this NVMe, slower than zram). A small disk swap *behind* zram for the desktop's
idle pages is possible and is the maintainer's choice; it is not part of the build.

**Order of the test arms** (RT on; walking, or his play: a standing route does not show memory in frames, 0408 §A.2):
1. Ledger alone (1) at his current save, in the slow area: fills §1 and gives the orphan count. It decides 5 and 11.
2. 2 + 6 + 7 + 9: the low-risk set.
3. Add 8 and 3 together.
4. Add 4 (zero skip), his call.
5. 5, 10, 11 only as the ledger directs.

**Box reads to ask the top session for before any build** (one GO, no emulator running): `ulimit -l` inside the
distrobox; `/proc/<pid>/cgroup` of a past launcher's shape and `cgroup.controllers` of the user slice;
`/sys/kernel/mm/lru_gen/enabled`; `/sys/block/zram0/mm_stat`; `sysctl vm.swappiness vm.watermark_scale_factor
vm.page-cluster`; the "Unevictable" and "Mlocked" lines of `/proc/meminfo`.

### 4. The first build's kit (laptop, 2026-11-10, on the maintainer's "działaj"; not built, not run)

One edit of e11's main unit (the unit of his "e11 unpacked" binary 70df5cb1), in exp 0401's kit pattern. Every switch
is default off; with all off the binary does what e11's does, plus one config read and two early returns.

| Switch | Candidate | In this build |
|---|---|---|
| `BC5_GUARD_LEDGER=1` | 1 | Two journal lines every 10 s: pinned bytes, bytes under a view, **orphans**, per heap name pinned/reserved (top 12), the emulator's RSS, shmem, swap and faults, MemAvailable, Unevictable, Mlocked, PSI, GTT |
| `BC5_GUARD_MLOCK=pinned` | 2 | Each imported range is mapped once more read-only and `mlock`ed, 64 MiB a call, on the guardian's thread (nice 10). Off by itself when the memlock limit is not unlimited, with one line saying so |
| `BC5_GUARD_MLOCK=guest` | 3 | That, plus `mlock2(MLOCK_ONFAULT)` on the direct-memory views that are not eager |
| `BC5_GUARD_FILE=random,dontneed` + `BC5_GUARD_FILE_ROOT` | 6 | Open files under the game's directory get `POSIX_FADV_RANDOM`; `dontneed` drops their page cache when PSI passes the threshold, at most every 5 s. Done from the guardian's thread over `/proc/self/fd`, so no other unit is edited |
| `BC5_GUARD_PSI=<%>` | 10, in part | The threshold (PSI memory "some", avg10). Steps (a) for the game's files and (e) only |
| `BC5_GUARD_PIN_CAP=<MiB>` | 11, log only | One line each time the pinned total passes the cap by 64 MiB more. No admission yet |
| `BC5_GUARD_APPLY_MIN_MS=<ms>` | 7, the simple form | `learned_apply` at most once per that while the layout keeps changing; never put off right after a device reopen. Not the incremental pass |

*Left out, with the reason.* Freeing orphans (5), admission (11) and the rest of the pressure loop (10 b–d) wait for
the ledger's first numbers: they unpin or refuse memory, and which class to act on is the open question. The
incremental `learned_apply` (7 in full) is a rewrite of fault-critical code that the laptop cannot run. The zero skip
(4) is already in this binary under its own switch. Candidates 8 and 9 need no build.

*Limits of this build.*
- The guardian's "pinned" is the union of every range the import loop imported. A live `BC5_DIRECT_LAZY_RELEASE`
  cut is not seen, and a locked range it cut would stay resident: do not combine `MLOCK` with a live lazy release.
- `MLOCK=guest` can end in an OOM kill where today the game is slow.
- `APPLY_MIN_MS` delays a newly needed learned window by up to that time; a GPU fault in that gap is possible [I].
- The per-heap rows count a file range once per view, so views that share a range make rows sum past the total.

*Files.*
- `guard0412.inc`: the guardian. `mkguard0412.py`: the edit (four places, each anchor once, undo check; input pinned
  to e11's unit by md5 prefix f366ff7b, the only part of it the laptop has).
- `test0412.cpp`: CPU test of the pure part. `syn0412.cpp`: syntax check of the host part against stand-ins.
- `mk0412.sh`: the box build (atomic BOX-LOCK claim, `mk0411.sh`'s pattern; reuses exp 0411's `link0411.py`).
  `play-guard-0412.sh`: arms `base`, `ledger`, `low`, `guest` on e11's 70 words, RT on. `kit.sha256`.

*Checked on the laptop* (VS clang++ 22, `-std=c++20 -Wall -Wextra -Wshadow -Werror`):
- `test0412`: 49 of 49.
- `syn0412.cpp`: no diagnostics.
- `mkguard0412.py` on a stand-in (the unit extracted from patch 0001 at 0401's tip, d18b4482, with `--any-input`):
  four edits applied, undo exact; without the flag it refuses the stand-in; it refuses an already edited unit.
- `bash -n` on both scripts; `mk0412.sh` with an empty stand-in home stops at "the kit is not what was sent";
  the wrapper's 70 words equal `play-e11-0411.sh`'s.

*Not checked.* The edit against e11's real unit, the compile with the box's GCC, and everything at run time. The
anchors were read in patch 0001 and in the kit's edit scripts, none of which touches them; e11's unit itself is only
on the box.

### 5. Box reads and the build (2026-11-10 19:27–19:29, on the top session's GO; no emulator, BOX-LOCK empty)

*Reads* (one guarded ssh; the box idle, kernel 7.2.15-ogc1.1.fc45):

| What | Value | Meaning for the plan |
|---|---|---|
| MemTotal | 15,557,528 kB = 14.84 GiB | §1's "about 14.2 GiB" was low: with 12.05 + 0.27 GiB pinned and ~0.4 GiB of host copies, about 2.1 GiB is left, not 1.5 |
| memlock limit, host and container | 2,147,484 kB soft **and hard** (~2 GiB) | **`BC5_GUARD_MLOCK` cannot work as the box is**: the guardian will journal "memlock limit limited" and lock nothing. Raising a hard limit needs root (a system setting), so it is the maintainer's step |
| Unevictable / Mlocked, idle | 573 MiB / 50 MiB | Something already keeps 0.5 GiB unevictable with no emulator. The ledger prints this value in play: if it rises by the pinned size, the kernel already takes pinned pages off its lists, link 2 of §2 is wrong and `MLOCK=pinned` is not needed |
| `lru_gen/enabled` | 0x0007 | multi-gen LRU is on; [K] in §2 was reasoned on the classic lists |
| `vm.swappiness` | 60 | the default, not a zram-tuned 180 |
| `vm.page-cluster` | 3 | swap-ins read 8 pages at a time; on zram that is extra decompression. Candidate 9 stands |
| `vm.watermark_scale_factor` | 10 | the default |
| zram `mm_stat`, idle | 568 MB stored as 127 MB (4.5:1), 205 MB used | §1 assumed 3:1; the store is cheaper than estimated at this ratio (idle desktop data; the title's pages may compress worse) |
| user slice `cgroup.controllers` | cpu io memory pids dmem | the memory controller is delegated: candidate 8 is possible without root |
| container compiler | g++ 15.2.0 (the unit's own command is clang's) | — |
| e11's unit | f366ff7bfc2c15a81cb9a5d091de6168; each of the four anchors and e11's reopen counter occurs once | the edit applies |

*Build* (`mk0412.sh` 26c941be, claim 19:28:20, release 19:29:00; shared builds and exp0401e8/0409/0411 only read):
- unit f9745c9f3d44164e36c5262a29cf2ef8 (from e11's f366ff7b), kit as `kit.sha256`;
- CPU test on the box: 49 of 49;
- **binary 70a3bbeee1afe9b1cf54a83d7982c600** at `~/bc5-work/exp0412/bin/kyty_emulator`; 5 warnings, the same 5 as e11's
  build, none from the guardian;
- launcher `play-pkg-0412.sh` 12838195c7ae2b6cc2b37912d74e198d (exp 0411's with its binary and log changed);
  wrapper `play-guard-0412.sh` ab4f167e. No shortcut was made and nothing was started.

### 6. The two shortcuts (2026-11-10 19:32, the top session's order; no emulator started)

`install0412.sh` on the box (atomic BOX-LOCK claim, released; from `~/bc5-work/exp0412/stage-20261110-1932`):
- *Wrapper* `play-guard-0412.sh` b1f82b9e (the first one, ab4f167e, is kept as `.before-sampler-ab4f167e`). It now pins
  the binary 70a3bbee and the launcher 12838195, checks the launcher's `ulimit -c 0`, refuses to start beside a running
  emulator, and starts the read-only sampler `sampler0412.sh` (a byte copy of exp 0401's `sampler0411.sh`, 9dfc33ee;
  exp0411 untouched) on the host. The sampler writes `~/bc5-work/exp0412/sampler/play-<time>-<arm>.txt` every 5 s and
  ends with the emulator's process.
- *Stand-in checks on the box, nothing started:* the wrapper's `dry` word for `ledger` (71 words) and `low` (77 words)
  printed the guardian words, "sampler pinned" and "nothing started" (`raw/dry-*.out` on the box); the sampler against a
  12-s stand-in process of its own wrote 2 lines and its end line. On the laptop: all four arms and the refusals
  (wrong binary, unknown arm, unknown second word, wrong wrapper md5 for the shortcut script).
- *Shortcuts* in `~/Pulpit`, by `shortcut0412.sh` 5fd31b08 (`shortcut0411.sh`'s pattern; the other shortcuts untouched):
  "BC5 emulator (0412 ledger)" ee484779 and "BC5 emulator (0412 low)" 2e5c2e9b. RT in the shared settings: on.
- In `low`, `BC5_GUARD_MLOCK=pinned` is inert while the memlock limit is 2 GiB (§5); the journal says so.

### 7. The first two plays and the ASTRO BOT kill (2026-11-10 21:47–22:35; read at 22:36, box free, read-only)

Raw: `raw/play-20261110-214740-ledger.txt`, `raw/play-20261110-215006-low.txt` (the sampler), `raw/ledger-2147.txt`,
`raw/ledger-2150.txt` (the guardian's lines of the two journals), `raw/oom-astro-20261110-223451.txt` (the kernel's
report). [M] measured, [I] inferred.

**The two plays of the second title** (build 70a3bbee, RT on, his save; ledger 21:47:40–21:50:03, he quit, exit 0;
low 21:50:06 until the box stopped answering, last journal line 21:52:58, manual reset).

| t (ledger arm) | pinned direct MiB | of it orphans | GTT | available | swap used | emulator RSS / shmem | PSI full % |
|---|---|---|---|---|---|---|---|
| 30 s (menu) | 8,438 | 5 | 9,049 | 3,662 | 553 | 2,166 / 1,930 | 0.0 |
| 60 s (save loaded) | 11,282 | 12 | 12,008 | 871 | 801 | 4,653 / 4,452 | 5.6 |
| 70 s | 11,284 | 2,145 | 11,938 | 838 | 788 | 3,370 / 3,170 | 2.0 |
| 100 s | 11,762 | 180 | 12,505 | 375 | 830 | 5,711 / 5,503 | 5.1 |
| 120 s | 11,988 | 406 | 12,715 | 372 | 1,061 | 63 / 21 | 19.5 |
| 130 s | 12,070 | 483 | 12,820 | 190 | 1,014 | 507 / 406 | 32.8 |

- **Which heap** [M], at 130 s, pinned/reserved MiB: AMM 2,967/2,967 (eager), RenderGpuWcLarge 2,758/2,758 (eager),
  CommitIABufferAllocator 2,736/2,736 (eager), AssetHeap Large 650/816 (by data), RenderGpuRwLarge 414, InitAllocator
  412/652, DynamicHeap 328, AssetHeap Small 280/350, Physics 192, anon 177, RenderGpuWcSmall 110, ComponentHeap 104,
  24 more 458/592; plus 270 MiB private. The only heap that grows with the save is **AMM: 496 MiB in the menu, 1,418
  at 40 s, 2,967 at the end** (+2.5 GiB). The two big render heaps are pinned whole from the menu on.
- **Orphans** [M]: 5 MiB in the menu; 2.1 GiB for some seconds while the views are rebuilt after the load (70 s);
  then they climb again while he moves: 180 → 310 → 406 → 483 MiB in 30 s. From 100 s on the whole growth of the pin
  (+308 MiB) is orphans (+303 MiB): memory the title gave back and the host keeps pinned.
- **Unevictable** [M]: 572–573 MiB all the time, with 12 GiB pinned. So the pinned pages are not on the kernel's
  unevictable list; they stay on the lists it scans. The emulator's mapped share of them falls from 5,503 MiB to
  21 MiB in 20 s (100 → 120 s) while the pin does not move, and the process takes 40,000–70,000 minor faults a second
  to map them again. This is section 2's link 2, now measured on kernel 7.2.15: the kernel unmaps pages it can never
  free. An mlock of the pinned ranges addresses exactly this; the limit change (memlock, root) is worth making.
  It frees no memory.
- **How fast, and what took the box down** [M]: 3.6 GiB available in the menu, under 0.9 GiB 57 s after the start,
  0.2–0.4 GiB from 100 s. PSI full over 25 % at 122 s (ledger), 86 % at 173 s (low). Swap held only 1.0–1.1 GiB of
  7.4 GiB at the end: the emulator's own memory outside the pin is about 0.3 GiB, so there was nothing left to swap.
  The kernel log of that boot has no OOM line and no line at all after 21:45 [M]; the box died in a reclaim storm
  without a kill [I: the last lines can be lost with the reset]. 12.07 GiB pinned + 0.27 private + the desktop do
  not fit in 14.84 GiB; the pin was still growing at 10 MiB/s when the play ended.
- **Did "low" change anything** [M]: before the wall, yes: 204 major faults by 80 s against 11,812, no swap-in until
  90 s against from 57 s, `learned_apply` ran 355 times against 932 (5,687 put off, no GPU fault in the log), 257
  files advised, 5 cache drops. The wall itself came at the same second (PSI 16–19 % at 120 s in both) and at the
  same pin. MLOCK did nothing (memlock limited, journaled). "low" trims the symptoms; it does not move the budget.

**The ASTRO BOT run** (21:58:04–22:34:51). It ran on the **shared build** 4d2b1b1d of 11-02 through
`play-astro.sh` with the shared `bc5-run.env`, not on exp 0409's binary: the menu script hands a game image to
`play-astro.sh`, whose `EMU` is the shared build (the play log's head says "emulator 2026-11-02 00:31:24") [M]. So
its memory words (13,824 MiB guest, eager GpuGarlicMemory/GpuOnionMemory, lazy orbis_user_malloc) are the old shared
ones, nothing new, and e8's objects, 0409's libAmpr and hostMenu were not in that process.

- Pinned [M, journal]: 8.65 GiB direct 78 s after the start, 8.78 GiB at 26 min, 8.95 GiB at the end; private 284 MiB
  throughout. The pin did **not** grow. It matches the kernel's shmem total, 9.49 GiB.
- What filled RAM and swap [M, OOM report]: the emulator's **anonymous** memory, 2.21 GiB resident + 5.09 GiB in
  swap = 7.3 GiB, and `bc5-mount`, 0.33 GiB resident + 1.14 GiB in swap = 1.5 GiB. The zram store held the 7.4 GiB of
  swap in 0.69 GiB (about 10:1), so the swapped data is highly repetitive.
- Rate [I]: no sampler ran beside it, so there is no time series. From about 0.3 GiB of host anon (the second
  title's figure after 2 min) to 7.3 GiB in 36 min is about 190 MiB/min on average. Steady or stepped is not known.
- Candidates [I], in the order the facts point: (1) something kept per submit or per journal line in the shared
  build with `PLAY_CAPTURE=1` (it sets `BC5_DIRECT_TIMING` and `BC5_DIRECT_FRAME_PROFILE`): the journal is 378 MB and
  3.43 million lines for this run, and 7 GiB / 3.43 M lines is about 2 KiB a line; (2) the mount's cache (1.5 GiB,
  package image through FUSE); (3) the tiler pool is ruled out (3 buffers, 96 MiB, 116,733 reuses) [M]; learned
  windows are ruled out (18 windows, pin flat) [M]. In the two 0412 plays the host anon stayed near 0.3 GiB over
  2 min, which is too short to see 190 MiB/min against the noise.

**Two different problems.** The second title hits a wall of pinned memory within 2 minutes (a budget, not a leak).
ASTRO BOT's pin is flat and something anonymous in the host grows for half an hour (a leak, in the shared build).

**Next step recommended**: one more private build (fixes first, each behind its switch), on this kit:
1. **orphan release** (`BC5_GUARD_ORPHANS`): unpin chunks no view covers, after a hold time. Measured prize 0.4–0.5 GiB
   and rising at the wall, 2.1 GiB during the rebuild.
2. **the pin cap enforced** (`BC5_GUARD_PIN_CAP` acts: release orphans first, then refuse lazy/learned growth), so
   the play degrades inside the game and the box stays alive.
3. **AMM by use** (zero skip limited to the AMM heap): the one heap that grows, 2.97 GiB pinned whole; its untouched
   share is not measured, and F403's hang risk applies, so default off and the last arm.
4. the sampler with two more columns: the emulator's and bc5-mount's anonymous + swapped MiB (`RssAnon`, `VmSwap`),
   and the same sampler beside one ASTRO BOT play with `PLAY_CAPTURE` off and one with it on. That decides the leak.
Outside the build: raise the memlock limit (root, the maintainer) so `MLOCK=pinned` can be tested. The cgroup words
(`memory.swap.max`, `memory.low`) and a PSI loop do not help the second title: there is nothing swappable to protect
or shed (1 GiB of swap in use at the wall). A cgroup `memory.max` on the emulator's scope would have turned ASTRO BOT's
36-minute fill into an early kill of the emulator alone; it is a safety net, not a fix.

### 8. The second build, g412b (2026-11-10 night, the top session's order; built and checked by stand-ins, not run in play)

Five items, each behind its own switch, all default off. Files: `guard0412.inc`, `mkguard0412.py`, `test0412.cpp`,
`syn0412.cpp` (edited), `mk0412b.sh`, `install0412b.sh`, `play-guard-0412.sh` (edited), `play-astro-guard-0412.sh`,
`sampler0412b.sh`, `fuse0412.sh`, `shortcut0412b.sh`.

| # | Item | Switch | What it is |
|---|---|---|---|
| 1 | Orphan release | `BC5_DIRECT_LAZY_RELEASE=10,eager` | **Already in e11's unit**: exp 0401 e7's lazy release (`lzr0401.inc`), which cuts a chunk under no view for the idle time, not forced, out of its BO and imports it again when a view covers it. Exp 0401 only ran it `dry` (170 MiB idle at the save of that day); this is its first live arm. No new code. `eager` is needed because the orphans are AMM chunks, last seen under an eager view. |
| 2 | The pin cap acts | `BC5_GUARD_PIN_CAP=<MiB>` + `BC5_GUARD_CAP_ACT=1` (+ `BC5_GUARD_CAP_NAMES`, default `AMM`) | New. When a sync's imports would take both files' pinned total over the cap, the **soft** chunks are put off: chunks wanted only for holding data, or by an eager heap named in the list, and not forced by a hint or a learned window. Every view over a put-off chunk gets the 2 MiB zero buffer (the scratch BO of exp 0037), so the GPU reads zeros and never faults. Hard chunks (the render heaps, forced windows) are imported as before. Each full sync asks again, so a put-off chunk comes in when the orphan release has made room. |
| 3 | AMM by use | `BC5_GUARD_AMM_BY_USE=1` (the launcher) | The launcher takes `AMM` out of `BC5_DIRECT_EAGER_NAMES`, so its chunks are pinned when they hold data, not when mapped. F403's class of risk (a GPU access to an AMM page no CPU wrote faults, 14 s). Arm `amm`, no shortcut. The prize is unknown and likely small: the title maps AMM pages to fill them, and a memfd page once written stays "data". |
| 4 | Sampler columns | `sampler0412b.sh` | The emulator's `RssAnon`, `RssShmem`, `VmSwap`; the same of `bc5-mount`; `memory.current` and `memory.swap.current` of the emulator's cgroup. The ledger line also has `rss anon` and `cgroup` now. |
| 5 | The fuse | the wrappers; `BC5_0412_FUSE=0` leaves it out | `fuse0412.sh` sets `memory.max` 12,300 MiB and `memory.swap.max` 2,048 MiB on the container's cgroup (`.../libpod-<id>.scope/container`, whose files the maintainer's user owns) while the emulator runs, and sets both back to `max` when it ends (a marker file covers a helper that died). Past the limit the kernel kills the emulator, with `ulimit -c 0`. Nothing system-wide. The limit covers everything in the container while it stands. |

Two corrections to the first build, found while reading the unit: the ledger counted pinned bytes from its own
grow-only set, which would be wrong once the lazy release cuts chunks, so it now takes the BO list at the end of each
full sync (`guard0412_synced`); and the cap's log line uses the same totals.

**What the cap arm will look like** [I]: over 11,600 MiB the title keeps running and newly streamed assets can be
black or missing until memory comes back. GPU writes into a put-off chunk are lost. Whether the title's renderer
survives zeros in streamed data (for instance ray-tracing structures) is not known; the fuse covers the box.
Not covered by the cap: chunks the lazy release imports again under a returning view (a small, bounded path).

**Limits chosen** [I, from section 7's numbers]: the box needs about 2.2 GiB outside the emulator and the emulator
about 0.3 GiB outside the pin; 11,600 MiB of pin is where 0.8 GiB was still available (60 s), 12,300 MiB in the
cgroup is where the box began to die (120–130 s). Whether pinned pages are charged to the container's cgroup is
assumed, not measured: the ledger's `cgroup` field and the sampler's column will show it in the first play, and if
they are not, the fuse never fires and changes nothing.

**Built and installed** (22:52-22:57, box free, BOX-LOCK ours and released): CPU test 64 of 64 on the laptop and the box;
unit 52eba0ad (from e11's f366ff7b), 5 warnings as e11; binary `baf16ce2fe4530b09464ba717b7a44e3` (the first build 70a3bbee
kept beside it); launcher 7899c6dd (0411's + EMU, LOG and the AMM line; 17 eager heaps, 16 with the word). Stand-ins on the
box: every arm's dry run; the sampler against two renamed `sleep`s (10 groups, the new ones numeric); the fuse against a
700 MB eater in the container: limit 1,220 MiB with the cgroup at 920, the eater ended with 137, `oom_kill` 1 -> 2, both
limits back at `max`. The cgroup's `memory.peak` read 12,716 MiB, so the plays' pinned memory **is** charged to the
container's cgroup [M]. Shortcuts on the desktop: `BC5 emulator (0412 orphans)`, `(0412 cap)`, `BC5 Astro (0412 capture off)`,
`(0412 capture on)`; `(0412 ledger)` and `(0412 low)` stay and now run the second build. No emulator was started.

### 9. The unattended night (2026-11-10 23:03 – 2026-11-11 01:10; the maintainer's "Przez 3h działasz sam i robisz testy i nowe buildy aż znajdziesz poprawę", relayed by the top session)

**Setup.** `run0412n.sh` (after exp 0401's `run0401t.sh`): the second title on the guardian's build with the "e11
unpacked" words, RT on, a private copy of his current saves (one named snapshot, sum `1151e79071c72b17`, 131 files;
the list has one slot, so the route is cross, cross, cross, gated on the journal's frame profile), then exp 0379's walk
for the play time. Beside every run: `sampler0412b.sh`, the fuse (`memory.max` 12,400 MiB, `memory.swap.max` 1,024 MiB
on the container's cgroup) and the watchdog `wd0412.sh` (SIGKILL under 300 MiB available or over 60 % PSI full for
10 s). `series0412n.sh` and `chain0412n.sh` ran the arms on the box under `setsid nohup`; the laptop streamed the kernel
log. Raw files: `raw/night/<tag>-*` (the play logs are left on the box). `sum0412n.py` makes the lines below.
The box stayed alive all night; BOX-LOCK was claimed and released per arm.

**Builds of the night** (each from e11's unit f366ff7b by `mkguard0412.py`, CPU test `test0412.cpp` on laptop and box):

| Build | Binary | Adds | Why |
|---|---|---|---|
| g412b | baf16ce2 | the acting cap, the ledger's BO snapshot | section 8 |
| g412c | d32dfa89 | `BC5_GUARD_SPLIT=1`: the lazy release may split a BO although `BC5_DIRECT_ALIASES` is set; the sync that cut ends with `aliases_apply(true)` | a2orphans: 194 MiB of idle orphans, **0 cut**, "3 not split (aliases)". The launcher sets `BC5_DIRECT_ALIASES=1`, so exp 0401 e7's release could only drop whole BOs, and BOs are merged up to 1 GiB. `Device::free_shared` drops the freed BO's aliases; they came back only at the next rate-limited `aliases_apply` |
| g412d | ca106494 | `BC5_GUARD_FORGET=<s>`: a forced chunk under no view for that long leaves the forced set | z1zscan: 264 MiB "forced and under no view" after 5 min. Test 72 of 72. One more `-Wformat` warning than e11 (a `%lu` given an `unsigned long long`, same size) |

**What the runs showed** [M unless marked]. Times are the ledger's (seconds from the emulator's start); the load is at
101–103 s in every run. "After the load" is from load + 45 s to the end.

| Run | Arm | Play | Pinned at 240 s | Pinned at the end | Available min | PSI full mean / max | Major faults /s | Flips /s | Longest frame | End |
|---|---|---|---|---|---|---|---|---|---|---|
| q1ledger | ledger, fuse **12,000** | – | 11,824 | 11,824 | 680 | 38 / 45 % | 4,189 | **1.0** | 7,108 ms | route gate never passed: the cgroup thrashed inside its limit |
| a1ledger | ledger | 150 s | 11,966 | 11,966 | 300 | 5.0 / 12 % | 609 | 21.8 | 1,169 ms | full |
| a2orphans | orphans (g412b) | – | – | 11,940 | 344 | 8.4 / 11 % | 1,375 | 19.4 | 360 ms | the watchdog (then at 400 MiB) killed it at 167 s; nothing had been cut |
| a3cap | cap 11,600 (g412b) | 150 s | 11,676 | 11,762 | 357 | 2.7 / 8 % | 275 | 21.7 | 449 ms | full; up to 262 MiB put off onto the zero buffer, no GPU fault |
| z1zscan | orphans + split + zero scan (g412c) | 170 s | 11,948 | 12,016 max | 276 | 3.4 / 12 % | 750 | 21.4 | 746 ms | full; 16 cut passes; the scan listed 1,010 MiB |
| b1ledger | ledger | 300 s | 11,972 | 12,098 | 324 | 4.8 / 20 % | 554 | 21.9 | 1,144 ms | full |
| b2zo | zero skip + orphans + split | 300 s | 11,238 | 11,300 | 708 | 0.8 / 4.8 % | 2 | 22.1 | 541 ms | full |
| b3zo | the same | 300 s | 11,236 | 11,386 | 680 | 0.6 / 8.7 % | 56 | 22.5 | 457 ms | full |
| b4ledger | ledger | 300 s | 11,970 | 12,084 | 281 | 7.8 / 38 % | 1,249 | 20.6 | 2,006 ms | full |
| c1zof | zo + forget 20 (g412d) | – | – | – | 938 | – | – | – | – | **GPU ring timeout at 99 s**, on the save list before the load; the ring reset succeeded, the box stayed up |
| c2zo | zo (g412d) | 600 s | 11,462 | 11,528 | 421 | 0.4 / 6.4 % | 4 | 22.1 | 537 ms | full; pinned flat at 11,52x–11,54x from 360 s to 720 s |
| d1zof | zo + forget 20 | 600 s | 11,416 | 11,566 | 462 | 0.2 / 6.7 % | 10 | 22.3 | 638 ms | full; 62+ forced chunks forgotten |
| e1of | orphans + split + forget 20, **no zero skip** | 300 s | 11,838 | 11,884 | 287 | 4.3 / 26 % | 774 | 21.5 | 1,608 ms | full; 0.2 GiB less pinned than the ledger runs, the pressure as theirs |

- **11.5 GiB is pinned on the start screen** (t 60 s), before any key: the title loads the save's scene behind it.
  What section 7 took for his key press was this.
- **The cgroup limit alone keeps the box alive.** With `memory.max` 12,400 MiB the unchanged ledger arm ran 7 minutes
  with 0.3 GiB available and never came near the watchdog's 60 % PSI; without a limit the same arm took the box down at
  21:47. The window is narrow: at 12,000 the title ran at 1 flip a second, because the cgroup was at its limit from
  the start screen on and reclaimed its own pages. The limit is a fuse, not headroom.
- **Zero skip + orphan release (zo) removes the memory pressure**: 0.55–0.75 GiB less pinned, major faults from
  550–1,250 a second to 2–56, PSI full under 1 %, twice the available memory, the longest frame halved, and the pin
  flat for the last 6 of 12 minutes (c2zo). The list was scanned in this night at his save (`zero-list-0412.txt`,
  394055535228641d, 740 MiB of RenderGpuWcLarge and 270 MiB of CommitIABufferAllocator); 670–760 MiB stay skipped
  after 5 min and 484 MiB after 12 (hints and five canary hits take chunks back).
- **The frame rate did not move**: 22 flips a second and a 34 ms median in every arm that ran, with the GPU busy
  27 ms and the game thread 12–14 ms outside the host. In this scripted walk the title is GPU-bound once memory is
  not short; the base arm's extra cost is in its tail (the longest frames, 2.6–3.1 % of frames over 100 ms against
  2.1–2.6 %). His own plays of 11-10 (57–79 ms frames, 39–58 ms outside the host) had no cgroup limit; that state was
  not reproduced here, and whether zo fixes it is for his play to show [I].
- **The orphan release needs the split switch**, and with it cuts 16–31 times a run without a fault. Its own gain in
  this walk is small (orphans are 60–350 MiB; z1zscan against the ledger runs shows no clear difference in the pin).
  **The forget switch adds nothing measurable** (d1zof against c2zo) and is left off.
- **The cap arm works as designed** (no fault, the pin 290 MiB lower at 240 s, fewer faults); nobody looked at the
  picture. With zo the pin stays under 11,600 MiB, so the cap would not act.
- **Risk**: one GPU ring timeout in five runs with the zero skip (c1zof, at 99 s on the save list, no page fault in
  the kernel log, the reset succeeded), none in seven runs without it. Exp 0401 saw the same class 3 times in 19 arms
  with the skip. Five against seven runs cannot say whether the skip raises it.

So the lever is the zero skip; the orphan release and the forget switch trim 0.1–0.2 GiB.

**ASTRO BOT, the leak** (`astro0412n.sh`; the shared build 4d2b1b1d through the private launcher copy, no input, the
title left where it starts, 600 s each, sampler every 5 s) [M]:

| Run | PLAY_CAPTURE | Emulator anon + swap | Rate | bc5-mount | Available | Flips /s |
|---|---|---|---|---|---|---|
| ao1off | off (no journal) | 652 MiB at 124 s → 2,256 MiB at 567 s | **217 MiB/min** | 1,491 MiB, flat | 2,841 → 1,200 MiB | see `raw/night/ao1off-fps.txt` |
| ao2on | on (journal 104 MB) | 625 MiB at 120 s → 2,362 MiB at 599 s | **218 MiB/min** | 1,489 MiB, flat | 2,713 → 1,144 MiB | see `raw/night/ao2on-fps.txt` |

- The leak is **steady** (a straight line, about 3.6 MiB a second), it is there **without any input**, and
  **PLAY_CAPTURE is not its cause**: the rate is the same with the journal off. Section 7's first candidate is out.
- `bc5-mount` holds 1.49 GiB from the first sample and does not grow: a cache, not a leak.
- At 217 MiB/min the 36-minute play of 11-10 comes to 7.8 GiB; the kernel's report had 7.3 GiB. The same thing.
- The second title on the e11-based builds does not show it: its anonymous memory stays at 130–300 MiB over 12 min.
- Not found: what allocates. Next step for that (not done tonight): the same idle start under `heaptrack` or with
  `MALLOC_` tracing in a private copy of the shared build, or a gdb sample of `malloc` callers at two times.

**The state for the morning.** On the desktop: `BC5 emulator (0412 zo - best of the night)` (zero skip with tonight's
list + orphan release with split + the fuse at 12,400 MiB, build g412d ca106494), beside `(0412 ledger)` (now with
the fuse), `(0412 orphans)`, `(0412 cap)`, `(0412 low)` and the two `BC5 Astro (0412 capture ...)`. Wrapper 3818e03f.
The frame profile files (`*-frames.txt`, 2.8 MB) and the play logs stay on the box in `~/bc5-work/exp0412/night/raw`.

**Not done / open.**
- Nobody has seen a picture of any arm. The cap arm's zeros and the zero skip's canary slices can show as missing or
  wrong textures; his eyes decide.
- The walk is not his play. His slow frames (57–79 ms) were not reproduced under the cgroup limit, so the frame-time
  gain of zo in his area is unmeasured.
- The GPU ring timeout class with the zero skip: 1 in 5 tonight.
- The memlock limit is still 2 GiB, so `MLOCK` was not tested.
- The ASTRO BOT leak's source.
- The zero list is a file beside the build (`~/bc5-work/exp0412/zero-list-0412.txt`), scanned over 2 minutes of one
  walk. A longer scan in his own play would list less and be taken back less.

### 10. Where ASTRO BOT's host memory grows (2026-11-11 01:06–01:28, the top session's order; three more runs, read-only tools)

Runs ao3off (510 s), ao4off (300 s), ao5off (240 s): the shared build 4d2b1b1d through the private launcher copy,
capture off, no input, fuse and watchdog on. Tools: `smaps0412.sh` (reads `/proc/<pid>/smaps` every 30 or 10 s), one
`eu-stack` snapshot, and `strace -k -e trace=mprotect,mmap` for 25–40 s from the ubuntu container. Raw:
`raw/night/ao3off-smaps.txt`, `ao4off-*`, `ao5off-*` (the traces gzipped).

- **Which mappings** [M, ao3off]: the growth is all in anonymous private memory, 398 MiB at 60 s → 1,913 MiB at 480 s.
  `[heap]` stays at 7 MiB. Threads (118) and file descriptors (174) are constant; the mapping count goes 972 → 993.
  The growing regions are 64 MiB-aligned blocks of 63–128 MiB, one below the other from 0x7efe60000000 down to
  0x7efe08000000: **glibc malloc arena heaps of one arena**, 8 such blocks at 90 s and 24 at 480 s. So it is `malloc`
  / `operator new` on a thread that is not the main one, never given back. The guest's memfd mappings do not grow.
- **Which thread and call path** [M, ao4off and ao5off]: of the heap growth the traces caught, 93–98 % is on one
  thread, **`bc5-cq0`** (BC5's completion thread of queue 0, `Libs::Bc5Gc::Direct::completion_thread`), by two paths:
  1. `completion_thread` → `SoftCp::submit` → `SoftCp::execute` → `SoftCp::fire` → the host's end-of-pipe event code
     in `src/graphics/host_gpu/renderer/sync.cpp` (addresses that resolve to lines 144 and 169, the functions around
     `TriggerAgcUserInterrupt`) → `operator new`: 6.1 of 10.2 MiB in ao5off, 1.6 of 2.9 MiB in ao4off, in 4 KiB steps;
  2. `completion_thread` itself → `operator new` (a container growing inside it; the address resolves into
     `bc5LleAgc.cpp`): 3.9 of 10.2 MiB and 1.1 of 2.9 MiB.
- **What the code at path 1 does** [M, source read; the link to the leak is I]: an event trigger
  (`EopEventTriggerFunc` in sync.cpp, the same pattern in `src/kernel/eventQueue.cpp` for user and AMPR events) does
  `event->pending_events.push_back(triggered_event)` whenever the event is already triggered and not yet read; the
  queue is a `std::deque` with no bound, and one entry is taken off per read (`eventQueue.cpp:130`). An event the
  title reads more slowly than the soft CP fires it, or never reads, grows by one entry per fire for ever. A real
  kqueue keeps one pending state per event, not a list.
- **Not shown** [open]: the byte rate through each path (the trace slows the title, and it caught 10 MiB where the
  process grew about 31 MiB); which event's queue it is; what the second site in `completion_thread` appends to.
  The inlined frames make the exact line uncertain.
- **The second title does not have it** [M]: its emulator's anonymous + swapped memory moves 1.5–2.2 MiB/min in
  c2zo, d1zof and b1ledger (g412d and e11-based builds, 4–9 min each), against 217 MiB/min here.
- **Fix candidate** [I]: in a private build of the shared source, bound `pending_events` (coalesce a trigger into
  the last pending entry when the queue is longer than a small number, or keep only the latest) behind a default-off
  switch, journal the longest queue per event, and repeat ao1off: the slope and the journal line name the event. The
  second site needs the same treatment once named (`addr2line` on a build with the unit's line table, or a counter).
- **A side effect of mine**: in ao5off I attached `strace` to the emulator's `bc5-*` threads, the ring thread among
  them. 10 s later the kernel logged a gfx ring timeout; the ring reset succeeded and the box stayed up. The title did
  not draw again in that run (anonymous memory flat from 131 s). Tracing the ring thread stalls submissions past the
  2 s fence timeout: do not attach to `bc5-ring`. ao4off's trace of every thread did not trip it.

The box at 01:28: no emulator, no mount, BOX-LOCK empty, the cgroup's limits at `max`, no fuse marker.

### 11. The events cap: ASTRO BOT's leak is the graphics events' pending queues (2026-11-11 08:58–09:25; the maintainer's "Tak, buduj")

**The change** (`events/`: `event_cap0412.hpp`, `mkev0412.py`, `evcap0412.cpp`, `mkev0412.sh`, `play-astro-ev-0412.sh`).
`mkev0412.py` edits copies of two host units of the shared source (pinned by md5; `~/src/KytyPlus` is only read):
the two places that did `event->pending_events.push_back(...)` for an already triggered event (`EopEventTriggerFunc`
in `sync.cpp`, `AmprEventTriggerFunc` in `eventQueue.cpp`) now call one function, `KernelEventPendingPush`. Two
switches, default off, and with both off it is the same `push_back`:
- `KYTY_BC5_EVENT_PENDING_CAP=<n>` (1..65536): an event's pending queue holds at most n entries; a trigger past that
  replaces the newest entry, so the triggers are coalesced and the latest data is kept.
- `KYTY_BC5_EVENT_PENDING_LOG=1`: names the event whose queue reaches 64 entries and each doubling, and with the cap
  the 1st, 2nd, 4th, ... coalesced trigger.
No header changes, so `KernelEqueueEvent` keeps its layout and no other unit is recompiled.

**Build ev412** (box, 09:03, BOX-LOCK ours and released): CPU test 1025 of 1025 on the laptop and the box; edited
units cba001bc (eventQueue.cpp) and 06c1349c (sync.cpp); exp 0401 e8's `build0401.py` compiled them and the tree's
unchanged `bc5LleAgc.cpp` with the shared build's commands and linked them with the shared build's other objects;
6 warnings; binary `f0120ffe73b9e9033ad8671c14fb5ffc` at `~/bc5-work/exp0412/ev/bin/kyty_emulator`. The shared build
is still 4d2b1b1d. Launcher `ev/play-astro-ev0412.sh` 894cf30b (exp 0412's astro copy with EMU and LOG changed).

**The pair** (`astro0412n.sh`, 600 s each, no input, capture off, sampler, fuse 12,400 MiB, watchdog; both on the
private build, so the only difference is the cap) [M]:

| Run | Switches | Emulator anon + swap | Rate | Available | Kernel lines |
|---|---|---|---|---|---|
| ev1log | LOG=1 | 629 MiB at 120 s → 2,368 MiB at 599 s | **217.8 MiB/min** | 2,730 → 985 MiB | 0 |
| ev2cap | CAP=64, LOG=1 | 212 MiB at 120 s → 213 MiB at 600 s | **0.1 MiB/min** | 3,338 → 3,312 MiB | 0 |

- **The events** [M, the log]: all with filter −14 (the graphics filter), no user data. In ev1log the longest queues
  passed 33,554,432 entries for ident 0x0 (the queued graphics interrupt), 8,388,608 for 0x40 (EOP), 524,288 for 0x46
  and 262,144 for 0x48; the lines come at powers of two, so the true lengths are up to twice that. In ev2cap the same
  four idents were coalesced as often. Over 40 million entries of 48 bytes are about 2 GiB, which is the growth.
- So the title, left on its start screen, does not read these events at the rate the soft CP fires them (tens of
  thousands a second for ident 0x0), and every unread trigger stayed in a `std::deque` for ever. A real kqueue keeps
  one pending state per event. The shared build has no bound; the leak is the host's, not the title's.
- **Section 10's second site** (`completion_thread` → `operator new`) was not a second leak: with the queues bounded
  the slope is zero, so those were ordinary temporaries landing at the top of an arena the queues kept growing [I].
- `bc5-mount` is flat at 1.47 GiB in both runs, as before.

**Not shown.** Nobody looked at the picture or played: the title stayed on its start screen in both runs, and the
play log has no frame counter for this title, so "the game behaves the same with the cap" is not measured. A title
that does read these events slowly would now see at most 64 old ones and then the latest, where it used to see every
one in order; whether ASTRO BOT ever depends on that is not known. The second title was not run on this build (it runs
on the e11-based builds, which have their own event-queue changes and no such growth).

**On the desktop:** `BC5 Astro (0412 events cap)` (`play-astro-ev-0412.sh cap`: the private build with CAP=64 and the
log, capture off, sampler, fuse). The shared build and its shortcuts are unchanged.

**Next, his call:** carry the two edits into patch 0001 with the cap on by default (a new shared build), after he has
played ASTRO BOT on this shortcut.

### 12. The second title, unpacked, on the events-cap build (2026-11-11 09:30–09:36; the maintainer: "do tej wersji dodaj możliwość uruchomienia rozpakowanej wersji drugiej gry")

No code change: the unpacked game is a launcher feature (`BC5_GAME_DIR` makes the launcher pass the directory to
`--game` instead of mounting the package; exp 0409's launcher and its descendants have it, the shared `play-pkg.sh`
does not). Added (`events/`):
- `ev/play-pkg-ev0412.sh` (box, e125fb4e): exp 0412's `play-pkg-0412.sh` with EMU = the ev412 binary and its own log
  (`~/bc5-work/exp0412/pkg-ev-last.log`); `BC5_GAME_DIR` and `ulimit -c 0` kept. Made and pinned by `startev0412.sh`.
- `play-pkg-ev-0412.sh cap|log|plain [dry]` (a8bde13f): runs it with `BC5_GAME_DIR=~/bc5-data/games/PPSA03671` and
  the arm's event words, with the sampler and the fuse (12,400 MiB) as the other wrappers.
- The shortcut `BC5 emulator (0412 events cap, unpacked)` (arm `cap`).

**What this build is.** ev412 is the shared source of 2026-11-02 plus the events cap. It has none of exp 0401–0411's
work (e8–e11: the reset and label switches, the table catcher, the ports) and none of the guardian's (ledger, zero
skip arm, orphan release with split). So the wrapper does not pass the "e11 unpacked" shortcut's 70 switch words: this
build does not know them. For his save's memory wall the shortcut to use stays `(0412 zo - best of the night)`.

**Start check** (`startev0412.sh s1cap cap 180`: the wrapper with a test copy of the launcher whose working
directory, save directory and learned file are private, no input, 180 s, watchdog, sampler, fuse) [M]: the title
started from the unpacked directory and drew for the whole time, 174 one-second fps lines, 28.0 flips/s, longest gap
255 ms; no crash line, no kernel line; available memory never under 2,450 MiB; the live saves' sum unchanged. It was
on the start screen: no key was sent, no save loaded, nobody looked at the picture.
The play log has **no event line**: in these 3 minutes no event of the second title was triggered while still unread,
so the cap did not act and this title's start screen does not have ASTRO BOT's growth on this build either.

**Not done:** a load of his save and play on this build; RT and the settings are the launcher's as usual. Whether he
wants the events cap in the e11-based line instead (the build the second title is meant to run on) is his call: the
two edits apply to that source as well, if its `eventQueue.cpp` and `sync.cpp` still have the two `push_back` lines.

### 13. The events cap in the e11-based line: build g412e (2026-11-11 09:36–09:45; the maintainer's "Tak, przenieś")

`events/mk0412e.sh`, `events/linkev0412.py`; `mkev0412.py` now also takes exp 0401 e8's `eventQueue.cpp`
(`--eq`, pinned d8eaa6d2: the e-series changed that unit with mkeq0405.py, and its two anchors and the one
`push_back` are still there). `sync.cpp` is the shared one (68733b6c); no earlier private build had it as its own
object, g412e does.

- **Build** (box, 09:39, BOX-LOCK ours and released): CPU test 1025 of 1025; edited units 64e176a7 (eventQueue.cpp)
  and 06c1349c (sync.cpp); 47 private objects (e8's, exp 0409's two, the two edited ones, g412d's main unit 5361c8ba);
  7 warnings (g412d: 6; the new one not read); binary `5db9b2e9805473ed3a01a96389087904` in place of g412d, which is
  kept as `bin/kyty_emulator.g412-ca106494`. The launcher is unchanged (7899c6dd). With the two event switches off the
  two functions do the `push_back` they did.
- **Arm `zoe`** in `play-guard-0412.sh` (wrapper 3ba549d5): zo + `KYTY_BC5_EVENT_PENDING_CAP=64` +
  `KYTY_BC5_EVENT_PENDING_LOG=1`. Every other arm runs the same binary without the event words.
- **Check** [M] (`run0412n.sh g1zoe zoe 120`: the scripted load of the copy of his save, 120 s of walking, sampler,
  fuse, watchdog): full run, no kernel line, no crash line. Pinned 11,230 MiB at 240 s (zo: 11,236–11,462), available
  never under 704 MiB, PSI full 1.8 % mean, 24.5 flips/s after the load, median 34 ms, longest frame 454 ms.
  The play log has the cap's announce line and **no coalesce line**: in this run no event of the second title had 64
  unread triggers, so the cap did not act. For this title it is a guard that costs nothing measured here, not a fix
  of something seen.
- **Shortcut**: `BC5 emulator (0412 zo + events cap)`. `(0412 zo - best of the night)` and the others stay; they now
  run g412e without the event words.

**Not done:** ASTRO BOT on g412e (the e11-based line was never his ASTRO BOT build; its leak fix is the ev412
shortcut of section 11). Nobody played or looked at the picture. One run of 4 minutes.

### 14. His plays of 2026-11-11 09:47–09:54 (logs collected at 09:56 on his word: "filmiki ingame ... bardzo niestabilne na każdej wersji")

Four starts from the shortcuts, all with the fuse at 12,400 MiB: zoe (09:47:17, closed after 6 s), the shared-source
build ev412 unpacked (09:47:33–09:49:26), zoe on g412e (09:49:37–09:52:12), zo on g412e (09:52:14–09:54:21, ended by
a GPU ring timeout at 09:54:16). Raw: `raw/play-20261111/` (the sampler files; per play the journal's memory lines
and one line per frame: t, frame ms, in-host ms, sync, hints, label waits, outside, GPU busy). The play logs, the full
journals and the device coredump `~/bc5-data/captures/devcoredump/20261111-095416-devcd3.txt` stay on the box.

**The same picture in all three plays** [M], in 15-s windows of the journal's frame profile:

| Window | What runs | Flips /s | Frame mean (max) | Game thread: in host (sync + hints) / outside | GPU busy |
|---|---|---|---|---|---|
| 15–30 s | the intro movies | 29.5 | 34 ms (44–60) | 3.5–3.8 (0.5) / 8–9 ms | 25–26 ms |
| 30–45 s | the scene behind the start screen loads | 11.5–12.6 | 79–86 ms (600–1,020) | 16–20 (9–13) / 51–53 ms | 14 ms |
| 60–90 s | the save loads | 6.9–8.9 | 111–150 ms (960–1,580) | 20–36 (11–30) / 69–112 ms | 8–13 ms |
| 105–120 s | play (zoe, zo) | 25–30 | 30–33 ms (450–470) | 13–14 (2.7–3.4) / 14–15 ms | 16 ms |
| 120–150 s | play (zoe) | 9–15 | 64–109 ms (330–1,909) | 21–45 (7–23) / 38–59 ms | 22–24 ms |
| 105–120 s | play (ev412, the shared source) | 0.7 | 492 ms (2,552) | 312 / 144 ms | – |

- **The intro movies are steady** (29.5 flips/s, no frame over 60 ms). What is unstable is everything after them.
- **While the title loads, the GPU waits for the CPU**: GPU busy 8–14 ms of frames of 80–150 ms. The game thread is
  50–110 ms a frame outside the host (the title's own loading work and its waits) and 16–36 ms inside it, of which
  the mapping work on every layout change (`sync` 6–21 ms, `hints` 2–11 ms a frame) is the larger part. In the zoe
  play `learned_apply` ran 993 times for 10.5 s in all and the merge pass 504 times, on the game thread, in 150 s.
  No memory pressure yet in these windows (PSI under 2 %, no major faults).
- **Then the memory limit** [M]: the container's cgroup is at 12,399 MiB from 40 s on in every play. From about 95 s
  the sampler shows swap-ins and swap-outs of 500–5,000 pages/s, 1,000–2,800 major faults/s and PSI full 5–15 %,
  available memory 300–600 MiB, and the emulator's mapped share of the pinned memory falls from 6.4 GiB to 1.0–1.4 GiB
  within 10 s (the kernel unmapping pages it cannot free, now inside the cgroup). The shared-source build, without
  the zero skip, was there first (11,792 MiB pinned, 0.7 flips/s at 105–120 s); zoe and zo got 20 s more
  (11,598–11,616 MiB pinned at 130 s, 596–762 MiB still skipped).
- So in his play the pin reaches 11.6 GiB within 130 s even with the zero skip and the orphan release. The night's
  scripted walk stayed at 11.2–11.5 GiB over 12 min; his route loads more, sooner. **The night's "no wall" does not
  hold for his play.**
- **The GPU reset** (09:54:16, zo): gfx ring timeout on thread `bc5-chainwd`, no page fault line, the ring reset
  succeeded; two submissions timed out at t 120 s. It is the second such timeout in 8 runs with the zero skip (c1zof
  in the night); 10 runs without it had none [M]. That makes the zero skip the likely trigger [I], as exp 0401's 3 in
  19 suggested. (The 01:25 entry in his notification list is the one my trace caused, section 10.)

**His two guesses against the data.** "Too many reads": yes after about 95 s, as major faults and swap traffic
caused by the memory limit, not before. "Something slows the frames": during loads it is the game thread, split
between the title's own work and the host's mapping work per layout change; the GPU is idle then.

**What follows** [I]: (1) the host's per-layout-change work on the game thread is the one cost present in every
slow window and on every build; `BC5_GUARD_APPLY_MIN_MS=50` (the "low" arm) cut `learned_apply` calls from 932 to
355 without a fault on 11-10 and was not in today's arms; (2) the memory budget is still over by 0.3–0.5 GiB in his
play, and the zero skip buys 0.6 GiB at the price of the ring timeouts; (3) the fuse turns a dead box into a slow
game, as designed, and is now the place where the thrash happens.

### 15. Where the threads' time goes, and the first fix of the host's memory bookkeeping (2026-11-11 10:10–10:39)

The maintainer after section 14: "Szukaj rozwiązania ... co jest źle zrobione przez co tracimy wydajność i dochodzimy
do ściany. Czemu gra poświęca tyle czasu na obliczenia? Nasze biblioteki są słabo napisane?" This section measures it
instead of adding another arm.

**The tool** (`prof0412.sh`, `prof0412.py`): a wall-clock stack sampler without perf or root. Inside the container,
`eu-stack -1 -p <tid>` attaches one thread for some milliseconds, 3–5 times a second (never a `bc5-*` thread, section
10); beside each sample the thread's CPU ticks, faults and context switches and the process's `/proc/<pid>/io`. A
sample of a blocked thread shows what it waits in, of a running one what it computes, so the share of samples per
call path is the share of the thread's wall-clock time. Runs: the scripted load of the copy of his save, ledger arm
(no zero skip), fuse and watchdog on. Raw: `raw/prof-20261111/`.

**What it found** [M] (run i1off / i4off, g412f with the fix off; h1ledger on g412e agrees):

| Thread, phase | Guest code | Waiting | Host library, running |
|---|---|---|---|
| game-main, scene load (33–62 s) | 29–33 % | 33–37 % | **24–31 % in `Ampr::AmmSubmitCommandBuffer`** (the title's AMM map/unmap commands) |
| game-main, save load (28 s) | 23–26 % | 34–37 % | **33–36 %** in the same |
| Render Thread, loads | 61–64 % | 6–13 % | 25–32 % in the GPU submit path (`Bc5LleKernel::Ioctl` → `chain_submit`, `submit_now`, `sorted_mappings`, `sync_mappings`) |

- **The game thread spends a quarter to a third of the load phases inside our AMM implementation**, and the innermost
  frames are bookkeeping, not system calls: `VirtualRanges::QuerySpan`, `PhysicalMemory::Unmap`,
  `KernelMapDirectMemory2`, `KernelSetVirtualRangeName`, `VirtualRanges::Remove`.
- **Why** [M, source: `src/kernel/memory.cpp`]: the host keeps the guest's address ranges in tables that are searched
  from the start on every operation. `VirtualRanges::m_ranges` is a sorted `std::vector` of 72-byte entries, about
  28,000 of them while the title streams (2 MiB); `QuerySpan` walked it from element 0 each time although the class's
  own `Overlapping()` uses a binary search; `Add`/`Remove` shift half the table per edit. `PhysicalMemory::m_mappings`
  is an **unsorted** vector: `Unmap` scans it, erases from the middle and scans it again (`still_mapped`);
  `SetVirtualRangeName` and `SetVirtualRangeMemoryType` scan all of it for every call. The title maps and unmaps 16 KiB
  pages by the thousand per second, so the cost per frame grows with the number of mappings: quadratic where the
  console does a page-table update.
- Every such edit also bumps the ranges' generation, which makes the direct path rebuild its 28,000 views (each with
  a `std::string` name), drain the GPU, recompute every mapping and run `learned_apply` (section 14: `sync` + `hints`
  6–30 ms a frame). Same class, second place.
- **Reads** [M, `/proc/<pid>/io` of the emulator in h1ledger, 270 s]: 1.10 million read calls, 19.9 GiB asked for,
  **44.6 GiB read from the disk**. During the loads 150–190 MiB/s are asked for and 310–440 MiB/s come off the NVMe;
  while walking, 59–74 MiB/s asked and 135–175 MiB/s read. The disk delivers 2.2 times what the title asks for: the
  files go through the page cache with read-ahead, inside a cgroup that is at its memory limit, so pages are read,
  dropped and read again. The title's reads go to its own buffers; the page-cache copy is ours.
  (About 2,200 of the read calls per second are tiny ones present even during the intro: pad, timers, sockets.)

**The first fix: `KYTY_BC5_RANGES_FAST=1`, build g412f** (`memfast/`: `mkmem0412.py` edits e8's `memory.cpp`
ee24c888 → 68c90f4b; `memfast0412.cpp` runs the old and the new walk on 200 random tables, 600,000 queries, the same
answers; `mk0412f.sh`, `linkmf0412.py`). `QuerySpan` starts at the range that holds the address (`std::upper_bound`);
the loop body is unchanged. Default off. Binary `8e42e0648031f09532d51c868ad8c309` in place of g412e (kept as
`bin/kyty_emulator.g412-5db9b2e9`); 47 private objects, 8 warnings (g412e: 7; the new one not read).

**A/B on g412f, ABBA** (i1off, i2fast, i3fast, i4off; the same scripted load, 60 s of walking) [M]:

| | off (i1, i4) | on (i2, i3) |
|---|---|---|
| Scene load: flips/s | 15.3 / 15.0 | **19.6 / 19.8** |
| Scene load: frame median, p95 | 55–57 ms, 157–158 ms | **27–30 ms**, 107–120 ms |
| Save load: flips/s | 12.1 / 11.6 | **15.6 / 15.6** |
| Save load: frame median, p95 | 64 ms, 161–202 ms | **47 ms**, 122–128 ms |
| game-main inside the AMM library, scene / save load | 24–31 % / 33–36 % | **8–11 % / 16–20 %** |
| Game thread outside the host per frame, scene / save load | 37–39 / 49–50 ms | 27–29 / 32 ms |

One changed loop start gives 30 % more frames in both load phases. No kernel line, no crash line in the four runs.
i2fast was ended by the watchdog at 167 s (available memory 299 MiB for 10 s at PSI 1 %): the faster load reaches
the memory limit sooner. That is the next wall, not a fault of the fix.

**What is still there with the fix on** [M]: game-main 8–20 % in the AMM library, now in `KernelSetVirtualRangeName`,
`KernelMapDirectMemory2`, `PhysicalMemory::Unmap` and `VirtualRanges` edits (the other linear tables); the Render
Thread 27–34 % in the submit path and 10–30 % waiting in it.

**Root causes and what fixes each** (in the order the data ranks them; [I] where it says "should"):
1. *The host's range tables are linear per operation* (measured above). Fix: `PhysicalMemory::m_mappings` indexed by
   address (an ordered map or a sorted vector with binary search, and a count per host mapping instead of the
   `still_mapped` scan), name and type edits by range lookup, `VirtualRanges` edits without shifting the whole table.
   Each as its own switch with an old-against-new CPU test on random operation sequences, as here.
2. *The direct path redoes everything per layout change* (views rebuild, GPU drain, full mapping diff,
   `learned_apply`). Fix: apply the delta of the changed ranges only; batch one AMM command buffer into one change.
3. *The submit path on the Render Thread* (a third of its time). Not opened yet; `sorted_mappings` and the per-submit
   filter are the first frames to read.
4. *Reads through the page cache* (2.2 times the bytes, inside the memory limit). Fix candidates: `O_DIRECT` reads into
   the title's buffers where offset and length allow, else `POSIX_FADV_RANDOM` plus dropping behind the read; either
   also takes the file cache out of the memory budget.
5. *The memory budget* (sections 7, 9, 14): the pin itself. With 1–4 the title loads faster and so hits it sooner
   (i2fast). The zero skip is the only lever measured and brings the ring timeouts; not solved here.

"Are our libraries badly written?" For this workload, yes in these places: correct, but with per-operation costs that
grow with the number of mappings, which this title drives to 28,000. The title's own share of the game thread in the
loads is a quarter to a third; it is not where most of the time goes.

### 16. The wall as arithmetic: the whole box at 165 s (2026-11-11 10:42–10:45, the top session's order)

`snap0412.sh` (read-only): `/proc/meminfo`, every process, every cgroup, the GPU counters and zram at 25, 60, 130 and
165 s of one scripted load of the copy of his save (run j1ledger: ledger arm on g412f, no zero skip, no orphan
release, fuse 12,400 MiB). At 165 s 296 MiB were available: the wall. Raw: `raw/prof-20261111/j1ledger-snap.txt`.

**MemTotal 15,193 MiB at 165 s** [M]; the lines sum to it:

| Line | MiB | What it is | Whose |
|---|---|---|---|
| Guest memory, pinned | **12,024** | 11,754 direct + 270 private (ledger); of it 320 orphans | the title's pools, except the orphans |
| Guest memory, not pinned, in RAM | 98 | Shmem 12,122 − pinned | the title's CPU heaps (the rest is in swap) |
| Kernel and GPU pages meminfo does not class | 893 | of it **583 = GTT 12,607 − imported 12,024**: the driver's own buffers (the emulator's and the desktop's; 465 at 25 s); about 310 more (vmalloc 115, the rest unnamed) | ours and the desktop's |
| File cache | 874 | Cached − Shmem. **In the container's cgroup: 42** (file 12,162 − shmem 12,120). The rest is the system's and the desktop's mapped files | system |
| Slab | 460 | 345 not reclaimable | kernel |
| Anonymous memory | 328 | the emulator 127 (+156 in swap), everything else 216 (+752 in swap; plasmashell alone 70 + 265) | ours 127, desktop 200 |
| zram's own RAM | 212 | holds 850 MiB of swapped pages | the price of the swap |
| Free | 167 | the kernel's reserve | – |
| Page tables | 108 | the emulator 67 | mostly ours |
| Kernel stacks, per-CPU | 28 | | kernel |

**Non-guest: 3,169 MiB, and it only fits because 986 MiB sit in swap and the game's file cache is gone.** What the
non-guest side wants when nothing is squeezed (resident + swapped): kernel/GPU 893, slab 460, page tables and stacks
136, zram 212, the emulator's own anon 283, the desktop and system 968 anon plus about 650 of mapped files: about
3,600 MiB, against 3,169 left by the guest. **The budget is over by roughly 0.4–0.5 GiB before the title's file
reads get a single page of cache.** That deficit is the wall; the fuse only decides whether the box or the emulator
suffers it.

**Ranked, with the fix per line:**
1. *Guest pinned, 12,024* — legitimate except **320 MiB of orphans** (memory the title released and we still pin; our
   defect). Fix: the orphan release with the split (g412c, arm `orphans`/`fast`), which needs no zero skip. The night's
   runs with it held the pin 0.1–0.2 GiB lower; in his play orphans were 440 MiB at 130 s with it on, so it does not
   yet cut all of them (forced chunks, chunks under partial views).
2. *Driver buffers outside the guest, 583* (465 before the save loads, so about 400–450 are there from the menu:
   the desktop's surfaces and the emulator's own swapchain, shadow, scratch and tiler buffers). Not broken down yet;
   needs the per-client numbers from `fdinfo` (`drm-memory-*`), readable without root. Open.
3. *Desktop and system, about 970 anon (750 of it in swap) + 650 mapped files.* A session without Plasma's shell
   (plasmashell 335, kwin 76, the portals and helpers) would return an estimated 400–500 MiB [I, from the per-process
   lines; not tried]. His decision.
4. *Slab 460 and the unnamed 310*: kernel; 12 GiB pinned as 3 million 4 KiB pages carries page arrays in the kernel.
   The guest memfd uses no huge pages (`shmem_enabled` is `never`; ShmemHugePages 0). Page tables are 108 MiB in all,
   so 2 MiB pages would save at most about 60 MiB there; what they would save in the pin's own bookkeeping and in TLB
   misses is not measured.
5. *The emulator's anon, 283* and *zram, 212*: small; zram returns four times what it costs.

**Three of the top session's expectations against these numbers:**
- *"The page-cache double is a wall item."* Not as resident memory: at the wall the container holds 42 MiB of file
  cache. The 44.6 GiB read for 19.9 GiB asked (section 15) are traffic and reclaim work, not occupancy. Reading
  without the cache (O_DIRECT or drop-behind) is a speed and I/O fix; it frees almost nothing at the wall. At 25 s the
  cache is 4.2 GiB, so it does delay the wall by filling memory early, but the limit already takes it back.
- *"memory.max is the wrong working limit."* Agreed on the mechanism, and the numbers show why moving it does not
  help: the cgroup is 12,400 = 12,024 pinned + 111 kernel + 125 anon + 42 file + the rest. The limit sits on the pin.
  Raised, the cgroup takes the box's last 296 MiB and the box is where it was on 11-10. A far fuse is right as a
  fuse; protection of the session (`memory.low`) only chooses who is squeezed. Neither creates the missing 0.5 GiB.
- *"Does the title take more than on the console?"* We offer 13,824 MiB of direct memory; the console's figure in exp
  0407's model is about 12,800. The title's views cover 11,435 MiB and it pins 11,754 here, under both. Whether it
  sizes its pools from the offer is not measured: the runs that offered less died in the host (the AMM window fault
  at 12,800, the TLS deaths at 11,776 and 12,288; section 3). Offering the true smaller budget needs those host bugs
  fixed first; that is the console-like answer and it is not done.

**What closes the gap** [I], in order of certainty: the orphans (0.3 GiB, ours, measured); a lighter session
(0.4–0.5 GiB, estimated, his call); the driver buffers once broken down; then the true guest budget. No single line
is the wall; the sum is.

### 17. Two short reads: the VRAM carve-out, and whether the mapping table's blocks ever overlap (2026-11-11 10:50–10:56)

**The carve-out** (the top session's question: could a smaller BIOS UMA return the missing 0.5 GiB?) [M]:
`mem_info_vram_total` 512 MiB (`vis_vram` the same), `mem_info_gtt_total` 13,312 MiB. `vram_used` is 48 MiB with the
box idle and 398 → 420 → 479 MiB at 25, 60 and 130–165 s of run j1ledger: 93 % full at the wall. Of the 1,191 MiB
that never reach Linux only 512 are the UMA; the other 679 are firmware and kernel reservations. A smaller UMA would
push the emulator's 430 MiB of VRAM buffers into GTT, which is system RAM: nothing gained. Which client holds the
VRAM at the wall was not read (the snapshot script has no `fdinfo` lines yet). Idle, the desktop holds 338 MiB of GTT
(plasmashell 167, plasma-keyboard 96, Xwayland 22, by `fdinfo`): part of section 16's 583.

**The overlap check, build g412g** (`memfast/mkphys0412.py`, `mk0412g.sh`; binary
`c8a3fd44bd5d17da69a158a6ab685e6f` in place of g412f, which is kept beside it). `PhysicalMemory::Unmap` takes the first
matching block in insertion order; a sorted table with a binary search is the same behaviour only if blocks never
overlap in guest addresses. `KYTY_BC5_PHYSMAP_CHECK=1` (default off, diagnostic, no behaviour change) compares every
block `Map()` adds with the whole table. Run k1check (the scripted load, 60 s of walking, `KYTY_BC5_RANGES_FAST=1`
too): **over 32,768 blocks added, none overlapped an existing one**; the table held 12,521 blocks at that point; the
run ended normally, no kernel line [M]. So for this title and this route a sorted table is valid. One run; the check
stays in the build for a longer one.

**Not done:** the sorted table itself. With `RANGES_FAST` on, `PhysicalMemory::Unmap` and the name edits are a few
percent of the game thread (section 15), less than the Render Thread's submit path (27–34 % of that thread), so the
submit path is the better next target by the numbers; the top session's order has the table first.

### 18. The sorted mapping table (build g412h) and the arm fast2 (2026-11-11 14:10–14:53)

**The fix.** `PhysicalMemory::m_mappings` (12,500 blocks at the save) was walked from its first element by `Unmap`,
`Find`, `SetVirtualRangeName` and `SetVirtualRangeMemoryType`. `KYTY_BC5_PHYSMAP_SORTED=1` (`memfast/mksort0412.py`,
helpers `memfast/physmap0412.inc`, tag ps412) keeps the table sorted by guest address and finds blocks by binary
search; `=verify` also runs the old search in `Unmap` and prints differences. A block that overlaps another, is empty
or wraps ends the sorted mode for the run (one line). Default off. CPU test `memfast/physmap0412.cpp`: 1,259,728
checks of old against new on random and adversarial sequences, on the laptop and on the box; it found one real case
(an empty-range `Unmap` breaks the order; that call now takes the old walk and the table is sorted again).
Build g412h = g412g + this, binary `0167c6c0`; g412g kept beside it.

**Runs** (`memfast/ab0412h.sh`; the scripted load of the copy of his save, arm ledger, `KYTY_BC5_RANGES_FAST=1` in all,
RT on, fuse 12,400 MiB, watchdog; data `raw/l*`). l1verify: no difference line, no overlap line, no kernel line [M].
ABBA l2off l3on l4on l5off [M]:

| | off (l2, l5) | on (l3, l4) | verify (l1) |
|---|---|---|---|
| scene load 33–62 s, flips/s | 19.8 / 18.3 | 23.1 / 21.5 | 21.9 |
| scene load, median / p95 frame ms | 30 / 120, 28 / 125 | 26 / 90, 28 / 98 | |
| save load 104–132 s, flips/s | 13.9 / 15.6 | 18.4 / 16.4 | 18.7 |
| game thread inside AMM bookkeeping, scene load | 15 % / 15 % | 4 % / 4 % | |
| game thread inside AMM bookkeeping, save load | 21 % / 17 % | 9 % / 19 % | |

Scene load +17 % frames (mean of two against mean of two), save load +18 % with one of the two "on" runs inside the
"off" spread: the scene-load gain is clear, the save-load gain is likely [M, two runs each]. Against g412e without
either fix (section 15: 15.0–15.3 and 11.6–12.1 flips/s) both fixes together give about +47 % in both phases [M].
Three of the five runs (l1, l2, l3) were ended by the watchdog at 146–166 s with less than 300 MiB available: the
ledger arm has no memory help, and a faster load reaches the limit sooner. No kernel line in any run.

**Per-client GPU memory** (`snap0412.sh` now reads `drm-memory-*` from fdinfo; l1verify at 130 s) [M]: emulator
GTT 12,071 MiB (two clients) and VRAM 431 MiB of the 512 carve-out (480 used in all); plasmashell 166 MiB GTT + 8 MiB
VRAM, plasma-keyboard 96 MiB GTT, Xwayland 22 MiB. The desktop's GPU memory is 285 MiB; the virtual keyboard's 96 MiB
is there on a box that has no touch screen.

**Arm fast2** = ledger + both table fixes + orphan release `BC5_DIRECT_LAZY_RELEASE=4,eager` + `BC5_GUARD_SPLIT=1` +
`BC5_GUARD_FORGET=10` + events cap 64; no zero skip. One scripted run, m1fast2 [M]: 24.2 flips/s over 208 s; the
release cut 1,548 MiB in 169 BOs over the run and 1,486 MiB came back under views (the title frees and takes again:
its AMM heap swings between 2,485 and 2,965 MiB about every 10 s on this route); at 182 s 12 MiB were under no view.
The pin stayed 11.5–11.65 GiB (ledger arm at the same point: 12.0 GiB, section 16), orphans by pages 120–250 MiB,
which are parts of 2 MiB chunks that still have a view and cannot be cut. So the release now works on his route
without the zero skip and what is left of the orphans is fragmentation, not a missed release. The run lasted 215 s
against 146–166 s for the ledger arm, then the watchdog ended it too (available 252 MiB): the budget is still short.
No kernel line.

### 19. The GPU path by source line (build g412i, 2026-11-11 14:53–15:07)

**Question** (the top session's order: the Render Thread's submit path, `chain_submit` / `sorted_mappings`; the
maintainer: "Ścieżka GPU"): what in the host's submission path costs the Render Thread its time, now that the two
table fixes are in.

**Setup.** Build g412i = g412h's code with line tables in the main unit (`-g1` through `BC5_0412_MAIN_EXTRA`,
`memfast/mk0412i.sh`; binary `a4dce942`, g412h kept). `prof0412.sh` with `PROF_SRC=1` takes inlined frames and source
lines; `prof0412src.py` sums them. Runs n1src, n2src (arm fast2, Render_Thread and game-main, 475 and 256 samples) and
o1aud (the title's audio thread, and the emulator's GPU engine time from fdinfo every 5 s). Data `raw/n[12]src-*`,
`raw/o1aud-*`. All three ended as scripted at 180 s, 24.6–25.2 flips/s, no kernel line.

**Result** [M unless marked]:

| share of the thread's wall-clock time | scene load | save load | play |
|---|---|---|---|
| Render Thread: guest code | 47 % | 35 % | 14 % |
| Render Thread: waiting | 29 % | 50 % | 61 % |
| Render Thread: host code | 22 % | 14 % | 23 % |
| game-main: guest code | 45 % | 27 % | 34 % |
| game-main: waiting (the title's own condition variables) | 48 % | 55 % | 57 % |
| game-main: host code | 6 % | 16 % | 7 % |

- The Render Thread's host code has no heavy line: the largest are the submit ioctl itself (2–4 %), the state
  tracker's copy and `apply_level` in `piece_check` (2–4 %), `emit_prefix` (1.5–3 %); `sorted_mappings` as CPU work
  does not appear. Every other line is under 1 %. A rewrite of this path can give a few percent of one thread.
- What the Render Thread waits for, over all phases: the flip's `drain()` (nothing of the frame may be in flight)
  20.5 %; the label waits in `submit_split` (a buffer waits for what an earlier one writes on the GPU) 10–13 %; the
  device and chain mutexes 12 % (`g_dev_mutex` at `submit_now`, the chain's flush mutex); the device's own lock inside
  `sorted_mappings` 3.5 %. The first two are the frame's CPU part and GPU part running one after the other.
- The emulator's GPU engine time (fdinfo, two readings of one counter halved; rough): 6–22 % of the wall clock in the
  scene load, 23–29 % at the start of the save load, about 55 % in play, 75–80 % in the menus. So the loads are not
  bound by the GPU, and no thread is at 100 % of a core either (game-main 50–65 %, Render Thread 40–50 %, the whole
  emulator 330–620 % of 1,600 %): the threads wait for each other and for the GPU in turn.
- The audio thread (`AK::AudioMgr`, 55–75 % of a core in play): 48 % of its samples are the title's own code (its
  software mix), 3 % host code (Opus decode in Ajm), the rest waiting. Not a host library's cost.

**What was not built, and why.** No change of the submit path: the profile names no line worth a switch. Deferring
the flip, which would remove the 20.5 %, was measured three times before (F68, F141, F226): the wait moves into the
label and in-flight waits and the second title's text breaks; not repeated. Open and named for the next step: who
holds `g_dev_mutex` while the Render Thread waits 12 % for it (the completion and ring threads are `bc5-*` threads,
which this sampler must not attach to; the host's own `BC5_DIRECT_TIMING` split or a lock-hold counter in a build
would say), and why game-main waits half its time in the loads (which of the title's threads it waits for).

**Memory, three more fast2 runs.** n1src, n2src and o1aud reached 180 s without the watchdog (the ledger arm: three of
five ended at 146–166 s, section 18); m1fast2 went on to 215 s and was ended there. The shortcut
"BC5 emulator (0412 fast2)" is on the desktop (build g412i in place).

### 20. Who holds the device mutex (build g412j, 2026-11-11 16:52–16:58, on the maintainer's "Tak, buduj licznik")

**Setup.** `BC5_GUARD_LOCK_STAT=1` (`memfast/lock0412.inc`, `memfast/mklock0412.py`, tag lk412; default off, then a
`std::mutex` behind one test): `g_dev_mutex`, which `submit_now` holds from its start to its end, counts per thread
name the locks, the time held and the time waited, and behind which holder. CPU test `memfast/lock0412.cpp`, 11 of 11
on the box. Build g412j = g412i + this, binary `c697e8cf` (g412i kept). One run, p1lock: arm fast2 with the counter
on, scripted load, 182 s, 25.0 flips/s (the same as without the counter), no kernel line. Data `raw/p1lock-lockstat.txt`.

**Result** [M], sums over the run's 180 s:

| thread | locks | held | per lock | waited for it |
|---|---|---|---|---|
| `bc5-ring` | 111,589 | 40.6 s (23 % of the time) | 0.36 ms | 17.0 s |
| Render Thread | 25,247 | 25.7 s (14 %) | 1.02 ms | 11.7 s |
| `bc5-chainwd` | 8,915 | 14.2 s (8 %) | 1.60 ms | 6.4 s |
| game-main | 4 | 0.3 s | | 0.6 s |

- The mutex is held 45 % of the wall-clock time and the three submitting threads together wait 35 s for it. In the
  heavy 10 s windows `bc5-ring` holds it 27 % and the Render Thread 22 % of the time.
- The Render Thread waits almost only behind `bc5-ring` (the thread that submits for the asynchronous ring);
  `bc5-ring` waits behind the Render Thread and `bc5-chainwd`.
- The longest single hold in a 10 s window is 35–135 ms in most windows after the start, with peaks of 354 ms
  (Render Thread), 186 ms (`bc5-ring`) and 152 ms (`bc5-chainwd`) in the save load; one of 1,501 ms by `bc5-ring` in
  the first seconds (start-up). Each is one or more whole frames with every other submitter stopped.

**Reading** [I]: every submission, from whichever thread, does all of its host work under this one mutex: the probe,
the mapping sync, the learned windows, the hints, the two filter passes and the submit ioctl (section 19 has their
lines). So the submitting threads run one at a time, which is the "threads wait for each other in turn" of section
19. The fix is not a faster line but a shorter hold: do what needs only the buffer (probe, filter, hints, the state
tracker) outside the mutex, keep under it the mapping sync and the ioctl, and find what the 35–354 ms holds are (the
forced sync or the learned windows, by the code). That changes the shared direct path's locking and needs its own
design and review; not built here.

### 21. The device mutex by part of the work (build g412k, 2026-11-11 17:43–17:48), and the design of a shorter hold

On the maintainer's "No to rób ten osobny projekt". Build g412k = g412j + `g_dev_mutex.mark()` at seven points of
`submit_now` (`memfast/mksect0412.py`; lock test 12 of 12; binary `e6d3a69e`, g412j kept). Run q1parts: arm fast2,
counter on, 179 s, 24.9 flips/s, no kernel line; data `raw/q1parts-lockstat.txt`. Of 77.8 s held [M]: the device call
(filter, state, BO list, CS ioctl) 36.1 s, direct sync 15.7 s, learned windows 8.9 s, anon sync 6.9 s, prepare 5.7 s,
the rest 4.6 s. The mapping maintenance (direct sync, learned, anon sync: 31.5 s) has the long single holds:
847 ms, 606 ms and 217 ms, against 246 ms for the device call and under 40 ms for the rest.

The design is `DESIGN-device-mutex.md`: stage 0 a catcher that puts long holds beside frame gaps, stage 1 the mapping
maintenance's kernel work outside the mutex with the submission order unchanged, stage 2 the buffer's own work before
the lock, stage 3 (the device call) left to an experiment on the backend. Expected gain: in the gaps over 100 ms
(51–61 s of each run have one), single percents in the mean frame rate [I]. Nothing of stages 0–3 is built.

### 22. Stage 0: the long holds beside the frame gaps (build g412l, 2026-11-11 17:51–17:56, the top session's order)

Build g412l = g412k + one journal line for every hold and every wait of the device mutex of 30 ms or more, stamped on
the journal's clock (`memfast/lock0412.inc`; lock test 16 of 16; binary `e07c8f57`, g412k kept; default off, no change
of behaviour). Run r1holds: arm fast2, `BC5_GUARD_LOCK_STAT=1`, scripted load, 181 s, 25.0 flips/s, no kernel line.
`holds0412.py` puts the holds beside the frames with more than 100 ms since the last flip. Data `raw/r1holds-*`.

**Result** [M]: 100 gaps over 100 ms, 18.0 s in all; 239 long holds, 13.9 s; 188 long waits, 10.8 s (Render Thread 3.1 s).

| phase | gaps | gap time | gaps with a long hold inside | with a long wait of the Render Thread inside | gap time the holds cover |
|---|---|---|---|---|---|
| scene load | 27 | 3.7 s | 14 (52 %) | 5 (19 %) | 0.7 s (19 %) |
| menu and list | 11 | 2.8 s | 6 (55 %) | 3 (27 %) | 0.4 s (13 %) |
| save load | 35 | 5.1 s | 19 (54 %) | 9 (26 %) | 1.1 s (22 %) |
| play | 23 | 5.9 s | 15 (65 %) | 5 (22 %) | 2.6 s (44 %) |
| all (with 4 in the menus) | 100 | 18.0 s | 56 (56 %) | 23 (23 %) | 4.9 s (27 %) |

The longest hold inside a gap is mostly `bc5-ring`'s or `bc5-chainwd`'s, in direct sync or anon sync; `learned` is
rare after the first second. 174 of the 239 long holds (9.0 s) lie in no gap.

**Verdict of stage 0.** The overlap is partial, not high: a long hold sits inside a little over half of the gaps but
covers 27 % of their time (44 % in play, about 20 % in the two loads), and the Render Thread itself waits long in a
quarter of them. Moving the mapping maintenance out of the mutex (stage 1) can at best shorten those gaps by that
share; three quarters of the gap time has another cause, which this catcher does not name (candidates [I]: the
title's own load work, memory pressure, the wait for the GPU at the flip). By the design's own rule stage 1 is not
prepared on this result; the decision goes back to the top session.

**The builds side by side** (flips/s by phase of the scripted run, from the frames files; the runs were made at
different hours, n1src–o1aud with stack samplers attached, so this is a comparison of runs, not one ABBA) [M]:

| arm and build | runs | scene load 33–62 s | save load 104–132 s | play 132–176 s | ended early by the watchdog |
|---|---|---|---|---|---|
| ledger, no table fix (g412f, off) | i1off, i4off | 15.3 / 15.0 | 12.1 / 12.8 | 18.0 / 21.2 | none |
| ledger + `RANGES_FAST` | i2fast, i3fast, l2off, l5off | 19.6 / 19.8 / 19.8 / 18.3 | 15.9 / 15.2 / 14.9 / 15.6 | – / 20.8 / – / 23.4 | i2fast 164 s, l2off 160 s |
| ledger + `RANGES_FAST` + `PHYSMAP_SORTED` | l3on, l4on | 23.1 / 21.5 | 18.4 / 17.2 | – / 20.8 | l3on 146 s |
| fast2 (both + orphan release 4 s + forget 10 s + events cap) | m1fast2, n1src, n2src, o1aud | 22.2 / 23.0 / 21.9 / 22.7 | 17.7 / 18.8 / 17.9 / 17.0 | 23.4 / 20.3 / 23.2 / 21.0 | none before 180 s; m1fast2 at 215 s |

(The save-load figures here count the window 104–132 s for every run; section 18's used each run's own load time.)
The table fixes show in the two loads; play is within the run-to-run spread for every arm. The orphan release
without the zero skip: works on his route since fast2 (section 18: 1,548 MiB cut over a run, pin 11.5–11.65 GiB
against 12.0, orphans left 120–250 MiB as parts of chunks still under a view); its effect is that no fast2 run hit
the watchdog before 180 s, where 3 of 7 runs without it did.

### 23. The frame gaps by cause (build g412m, 2026-11-11 18:02–18:12, the top session's order)

**Catchers** (no behaviour change, default off). In the host, `BC5_GUARD_GAP_STAT=<ms>` (`memfast/gap0412.inc`,
`memfast/mkgap0412.py`, tag gp412): every blocking point the host owns counts its time per thread and cause (the
device mutex, the chain's flush mutex, the drain at the flip, the label waits, the in-flight cap, the ring's wait-idle,
the completion thread's GPU fence wait and its wait for work), `submit_now` and `submit_split` count their own time
exclusive of those, and at each flip that ends a gap over the limit one journal line gives the per-thread milliseconds
with CLOCK_MONOTONIC. Outside, `gapsamp0412.py` reads `/proc/<pid>/task/<tid>/stat`, `schedstat` and `syscall` of the
Render Thread, game-main, `bc5-ring` and `bc5-cq0` every 20 ms (no ptrace). `gaps0412.py` joins the two. CPU test in
`memfast/lock0412.cpp`, 23 of 23 on the box. Build g412m = g412l + this, binary `b0921384` (g412l kept).
For a play from the shortcut: a file `~/bc5-work/exp0412/catchers.env` with the line `BC5_GUARD_GAP_STAT=100` turns
both halves on in `play-guard-0412.sh` (the sampler writes `sampler/gapsamp-<stamp>-<arm>.txt`); no file, no catcher.

**Run** s1gap: arm fast2, RT on, `BC5_GUARD_GAP_STAT=100 BC5_GUARD_LOCK_STAT=1`, scripted load. 26.1 flips/s over
138 s; **the watchdog ended it at 144 s** (available under 300 MiB; the first fast2 run to end before 180 s), so the
play phase is 12 s long here. No kernel line, no rsync on the box. 78 gaps over 100 ms, 13.6 s.
Data `raw/s1gap-*` (`raw/s1gap-gaps-by-cause.txt` is the full output).

**Where the Render Thread (the thread that flips) was during the gaps, share of the gaps' time** [M]:

| | scene load (19 gaps, 2.7 s) | save load (34, 5.2 s) | play (9, 2.4 s) | whole run (78, 13.6 s) |
|---|---|---|---|---|
| on CPU outside the host's GPU path (the title's code and the host libraries it calls) | 54.8 % | 47.2 % | 9.8 % | 46.6 % |
| on CPU in the host's GPU path (`submit_now`, `submit_split`) | 15.3 % | 16.7 % | 26.8 % | 15.9 % |
| blocked on the device mutex | 18.7 % | 13.7 % | 27.6 % | 18.2 % |
| blocked on the chain's flush mutex | 6.0 % | 10.2 % | 2.4 % | 6.2 % |
| blocked in a futex wait that is no host stamp (the title's own locks and waits) | 0.7 % | 2.1 % | 23.5 % | 5.6 % |
| waiting for the GPU: the drain at the flip | 2.8 % | 4.4 % | 2.0 % | 3.0 % |
| waiting for the GPU: label waits | 1.0 % | 4.2 % | 4.5 % | 2.8 % |
| run-queue wait, sleeps, not sampled | 0.7 % | 1.5 % | 3.4 % | 1.7 % |

(The first two rows are the on-CPU time of `schedstat`, 70.1 / 63.9 / 36.6 / 62.5 %, split by the host scopes' own
time; the scopes' time is taken as CPU time. Of the on-CPU ticks 89 % are user, 11 % system.)

The other threads in the same gaps [M]: game-main is on CPU 54 % and in a futex wait 45 %; `bc5-ring` is on CPU
28 % (43 % of it system time), blocked on the device mutex 21 %, in its own idle sleep 40 %; `bc5-cq0` waits for
work 89.5 % of the gap time and for a GPU fence 9.4 %. Major faults inside all gaps: Render Thread 425, game-main 200.
The block-I/O delay counter reads 0 for every thread (delay accounting is off on this kernel), so reads are seen only
as major faults and as the absence of any thread blocked in a read at the 20 ms samples.

**Reading.** (1) The GPU is not what makes the gaps: its completion thread has nothing to wait for 90 % of the gap
time, and the Render Thread's waits for the GPU are 6 %. (2) Nor is the disk, as far as this catcher sees. (3) In the
two loads the largest share, about half, is the Render Thread computing outside the host's GPU path: the title's own
frame work. (4) The host's part is 40 %: 24 % blocked on the two submission mutexes (the same quarter stage 0 found)
and 16 % in the host's submit path. In the short play phase the mutex and the title's own waits lead.

**Proposal.** The largest named cause is CPU time of the Render Thread outside the host's GPU path, and this
catcher cannot say whose code it is (the title's or a host library's). So the next step for that cause is one more
catcher, not a fix: the stack sampler of section 19 with the monotonic clock, joined to the gaps, to name the
functions inside the long frames. For the largest cause that is ours by name, the two mutexes (24 %), the fix is
stage 1 of `DESIGN-device-mutex.md` together with the chain's flush mutex, which the design did not yet cover;
its bound is that quarter of the gap time. Not built; the top session's review comes first.

### 24. The on-CPU time inside the gaps by function, and why fast2 now ends at 144–151 s (2026-11-11 18:14–18:27, the top session's orders)

**Setup.** `perfgap0412.sh`: perf's cpu-clock event at 1 kHz, user space, on the Render Thread and game-main only, on
CLOCK_MONOTONIC (perf_event_open: no ptrace, no thread stopped; leaf address with symbol and DSO, no call chains).
perf was installed in the ubuntu container for this (`apt-get update`, `linux-perf` 7.0.0-43; apt also moved the
container's `linux-libc-dev` to 7.0.0-43, a side effect to know of for later builds there). `gapstack0412.py` joins
the samples with the gap lines of section 23; `perftop0412.py` sums a thread's samples over a whole run.
Runs t1perf and u1perf: arm fast2, RT on, `BC5_GUARD_GAP_STAT=100`, build g412m. **Both were ended by the watchdog at
144 s, so the play phase is 12 s (13 and 4 gaps): its column is short and marked.** The perf text files (1.7 MB each)
stay on the box, `~/bc5-work/exp0412/night/raw/{t1perf,u1perf}-perf.txt.gz`; the join's output is `raw/*-gapstack.txt`.

**Result: the Render Thread's user-space CPU inside the gaps, % of the gaps' time (t1perf / u1perf)** [M]:

| | scene load (22 / 22 gaps) | save load (28 / 30) | play, SHORT (13 / 4) | whole run (87 / 76) |
|---|---|---|---|---|
| guest code (the title's own, no host symbol) | 40.9 / 46.9 | 39.7 / 33.2 | 27.9 / 10.2 | 45.5 / 44.8 |
| host GPU path (`submit_now`, `direct_sync_one`, state tracker, filter) | 2.9 / 5.5 | 6.9 / 4.8 | 3.4 / 5.4 | 3.9 / 4.2 |
| libc and libstdc++ (`memmove`, tree walks, `malloc`) | 1.1 / 3.5 | 6.6 / 3.8 | 2.8 / 3.5 | 3.2 / 3.4 |
| host memory, libkernel, loader, others | 0.4 / 1.4 | 1.5 / 0.6 | 0 / 0.4 | 0.3 / 0.4 |
| all user-space CPU | 45.6 / 57.6 | 54.6 / 42.7 | 34.5 / 19.7 | 53.4 / 53.4 |

No host function is over 2 % of the gap time on the Render Thread; the heaviest are `memmove` 1.2, `_Rb_tree_increment`
0.9, `submit_now` 0.9, `direct_sync_one` 0.6. So section 23's "47 % on the CPU outside the host's GPU path" **is the
title's own code** (45 %), and of the 16 % that section 23 counted inside the host's submit scopes only 4 % is our
user-space code: the other 12 % is spent in the kernel under those scopes (the submit and pin ioctls, page faults),
which user-space sampling does not see.
game-main inside the gaps (whole run) [M]: guest code 32.6 / 33.7 %, `memmove` 12.2 / 14.7 % (the title's copies,
through the host's libc), `Loader::TlsMainGetAddr` 3.0 / 3.0 %, `KernelGetProcessTimeCounter` 2.2 / 2.4 %, host memory
(memory.cpp, AMM) 1.1 / 0.9 %.

**The submit path's passes over the whole run** (`raw/u1perf-perftop.txt`; Render Thread, 65.1 s of user-space CPU in
137 s) [M]: guest code 63.6 %; `memmove` 5.3 % (3.5 s); `submit_now`'s own loops 3.6 % (2.4 s); the state tracker
`emit_prefix` 2.9 % + `apply_level` 2.2 % + `state_stack::apply_in_place` 0.9 % (3.9 s); `policy::filter` 1.4 %;
`Device::submit` 1.0 %; `indirect_check::apply` + `insert_before` 1.5 %; `direct_sync_one` 0.7 %; `catch_add` 0.7 %;
`submit_split` 0.7 %; `malloc` 1.2 %; number formatting for journal lines (`printf_fp`, `strlen`) 1.0 %. On game-main:
`TlsMainGetAddr` 3.6 % (2.4 s) and `KernelGetProcessTimeCounter` 2.2 % (1.5 s) of its user-space CPU.
The cheap candidates by these numbers: the state tracker's prefix (5 %, rebuilt per piece), the copies (5 %), the
two libkernel helpers on game-main (6 %). None is built yet.

**Why fast2 ends at 144–151 s since 18:02** (five runs of five: s1gap, t1perf, u1perf, the control v1ctl without any
catcher, w1perf; the afternoon's eight all passed 180 s) [M]:

| | afternoon (n1src, n2src, o1aud, p1lock, q1parts, r1holds) | evening (s1gap, t1perf, u1perf, v1ctl, w1perf) |
|---|---|---|
| available at 5 s | 3,900–4,100 MiB | 3,908–4,086 MiB |
| swap used at 5 s | 658–678 MiB | 672–676 MiB |
| pinned at 140 s | 11,570–11,668 MiB | 11,622–11,696 MiB |
| orphans at 140 s | 146–290 MiB | 195–269 MiB |
| available at 130 s | 348–447 MiB | 325–429 MiB |
| available at 135 s | 287–357 MiB | 243–370 MiB |
| available at 140–141 s | 274–329 MiB | 245–305 MiB |
| lowest available of the run | 260–289 MiB (o1aud, r1holds; one or two 2 s samples) | under 300 MiB for five samples in a row |
| watchdog, tools | 300 MiB, five samples of 2 s; `wd0412.sh`, `run0412n.sh`, `fuse0412.sh` unchanged since 2026-11-10 23:28 | the same files |

Whole-box snapshots at 130 s, m1fast2 (14:51) against w1perf (18:26), `raw/snapdiff-m1fast2-w1perf.txt`: no line of
`/proc/meminfo`, of the processes or of the cgroups moved by more than 76 MiB outside the emulator; MemAvailable was
76 MiB higher in the evening run at that moment; zram holds 37 MiB more; the login session's scope +51 MiB (the ssh
sessions that start the runs and perf), journald +16, podman +16.
**No line moved.** The pin, the orphans and the start state are the same; the release cuts as before. The arm always
dipped to 245–330 MiB at 135–141 s, where the save load ends; in the afternoon the dip lasted one or two samples and
the run went on, in the evening it lasts five (10 s) and the watchdog acts. The control without catchers ends the
same way, so neither the catchers nor build g412m is the cause. The difference is a few tens of MiB inside a margin
that was never there (section 16: the budget is 0.4–0.5 GiB short). Nothing is left full by earlier runs (swap and
zram are at their afternoon values), so there is nothing to reset; what would move the line is memory: the 96 MiB
virtual keyboard and other desktop parts (section 18), or the top session's choice of a lower watchdog threshold for
measuring runs. Neither was changed here.

### 25. Why the title's own code is slow in the play phase (run x1why, 2026-11-11 18:30–18:34, the top session's order)

**Setup.** One scripted run on arm fast2, RT on, build g412m, `BC5_GUARD_GAP_STAT=33` (a line for every frame over
33 ms), with: `gapsamp0412.py` (20 ms), `perfall0412.sh` (perf cpu-clock 1 kHz, every page fault with its address,
`perf stat` per thread every 100 ms; user space, two threads, no ptrace), `thr0412.py` (every thread's CPU, last CPU
and run-queue wait every 250 ms; MHz per core; k10temp; other processes; policy and affinity of all 102 threads at
150 s). The watchdog at 220 MiB for this measuring run by the top session's decision (`N_WD_MIB=220`; the fuse
unchanged). The run reached 179 s: **a play phase of 43.4 s, 927 frames, median 34.2 ms, p90 62.7 ms**, 24.6 flips/s,
lowest available 232 MiB, no kernel line. `why0412.py`, `spin0412.py`, `longfr0412.py` make the numbers below;
outputs `raw/x1why-why.txt`, `-spin.txt`, `-longframes.txt`; the large collector files stay on the box
(`~/bc5-work/exp0412/night/raw/x1why-*`).

**The table: the flipping thread's (Render Thread's) play time by cause** (frames over 33 ms are 86 % of the play
time, so the play phase as a whole is that time) [M]:

| cause | share |
|---|---|
| waiting for the GPU: the drain at the flip 17.3 %, label waits 9.0 % | 26.3 % |
| the title's own code on the CPU | 20.6 % |
| — of it a wait loop of some 40 bytes of code, in the frames over 100 ms | 5.6 % |
| the host's GPU path on the CPU, user space (`submit_now`, state tracker, filter, sync) | 11.0 % |
| kernel time on the CPU (the submit and pin ioctls, page faults) | 7.0 % |
| blocked on the device mutex 8.8 % and on the chain's flush mutex 7.9 % | 16.7 % |
| libc (copies, allocations; from the title and from the host) | 6.5 % |
| sleeping with no host stamp (20 ms samples) | 5.9 % |
| futex wait with no host stamp (the title's own locks) | 4.4 % |
| other host code 0.8 %, run-queue wait 0.5 % | 1.3 % |

The main thread in the same time: the title's code 48.3 %, a futex wait of the title's own 43.4 %, host libkernel
and loader 4.6 %, libc 2.0 %, kernel 0.9 %, run-queue wait 0.6 %.

**The ordinary play frame** (577 frames of 33–50 ms, mean 36.9 ms; mean ms per frame) [M]: the completion thread
waits for a GPU fence 21–24 ms (the GPU's work of the frame); the Render Thread waits 10.6 ms in the drain at the flip
and 4.8 ms in label waits, spends 5.8 ms in `submit_now`, 2.5 ms in `submit_split`, 3.0 ms on the two mutexes, and has
14.6 ms of user-space CPU of its own in the frame; the main thread has 19.0 ms. So the frame is the title's CPU part
and the GPU's part one after the other, with the host's 8 ms of submission between them: about 15 + 8 + 15 ms.
Neither thread is saturated (Render Thread on the CPU 46 %, main 56 %).

**The long play frames** (20 frames over 100 ms, mean 345 ms, 6.9 s = 16 % of the play time) [M]: the GPU is idle
(the completion thread has no work 315 ms of the 345); `bc5-ring` is 107 ms blocked on the device mutex and 91 ms in
`submit_now`; `bc5-chainwd` 53 ms in `submit_now` and 32 ms on the mutex; the Render Thread 75 ms on the chain mutex,
52 ms on the device mutex, 72 ms in `submit_now`. Meanwhile the title's two threads spin: of the Render Thread's
guest-code samples in these frames 94.6 % lie in one 4 KiB page, in about 18 addresses two bytes apart (IPC 0.37
there against 1.08 in the other frames), and 74 % of the main thread's lie in another single page. The same two loops
hold 21–29 % and 18 % of the samples in the other frames. **So "the title's own code" in the long frames is the title
waiting in a spin loop while the host's submission threads hold the device mutex for long (the mapping maintenance of
sections 21–22), not the title computing.** What exactly the loops poll is not read (it needs the bytes of the
title's code at that address).

**The six questions** [M unless marked]:
1. Counters, user space. IPC: Render Thread 0.94 in play (1.08 outside the frames over 100 ms, 0.37 inside them),
   main thread 1.05; in the loads 0.53–0.66 and 0.85–1.16. dTLB load misses 0.41–0.46 per 1,000 instructions in play
   (0.5–0.9 in the loads), iTLB 0.07–0.09, cache misses 7.7–8.6. The TLB is not what slows the title: large pages
   for the guest memory are not indicated by this, and what THP on the memfd would need was therefore not worked out.
2. Kernel time: 7.0 % of the Render Thread's play time (18 % of its CPU ticks are system), 0.9 % of the main
   thread's. Page faults: Render Thread 1,121/s, 58 % on the guest's direct memory from the title's code, 26 % in the
   host's `memmove` and 13 % in the direct sync's own vectors on host anonymous memory; main thread 720/s, 84 % on
   direct memory from the title's code. Major faults 58/s and 47/s. No thread was seen blocked in a fault at the 20 ms
   samples above 0.3 % of the time. The direct-memory faults are first touches after a mapping change (the AMM heap's
   swing and the release, section 18); at these rates they are not a cause of the frame time.
3. Signals: 301 of 166,012 user-space samples (0.18 %) lie in signal-return or handler symbols. The rate of signals
   itself was not counted (the tracepoint needs root).
4. Threads and cores: all 102 threads are SCHED_OTHER, nice 0, allowed on CPUs 0–15: whatever affinity and priority
   the title asks for, the host applies none (what the title asks was not read). The emulator uses 4.3 of the 16
   logical CPUs (8 cores) in play: the title's threads 3.4, the host's 0.9 (`bc5-ring` 27 %, `kyty-gpu` 11 %,
   `bc5-chainwd` 7 %, the four `bc5-apr` threads 21 %). Hottest: `AK::AudioMgr` 56 %, main 56 %, Render Thread 46 %,
   ten job threads 13–14 % each. Run-queue wait is at most 1.2 % for any thread. In 22 % of the 250 ms ticks with two
   hot threads, two of them sat on the two logical CPUs of one core. Outside the emulator: `kcompactd0` 30 % of a CPU
   (the kernel compacting memory), the collectors 8 %, KWin 2 %.
5. The CPU's clock: no cpufreq driver on this box; `/proc/cpuinfo` reads a median of 3,492 MHz, the lowest single
   reading 1,612 MHz, under 3,000 MHz in fewer than 0.5 % of the 704 readings; k10temp 73–75 °C. No throttling seen; throttle counters do not exist here.
6. Per frame, user-space CPU of the Render Thread / the main thread: frames up to 33 ms 13.8 / 16.7 ms; 33–50 ms
   14.6 / 19.0 ms; 50–80 ms 24.0 / 39.0 ms; 80–100 ms 23.2 / 63.0 ms; over 100 ms 144.5 / 207.8 ms (the spin loops).
   The title's threads are not saturated: nothing the box lacks in cores explains the frame time.

**What follows** [I]. Two different things make the play phase slow. (a) Every frame: the CPU part and the GPU part
do not overlap. The GPU works 21–24 ms a frame and the Render Thread waits for it at the flip and at label waits
(26 % of its time) instead of preparing the next frame; with the host's 8 ms of submission that gives 37 ms, where
overlapped it would be about 23. Deferring the flip was tried three times and failed on the label waits and the
text (F68, F141, F226), so the fix is not that switch again but what makes the title wait at its labels: to be named
next (which labels, written by which job, and why the title cannot run ahead). (b) The frames over 100 ms (16 % of
the play time): ours by measurement, the long holds of the device mutex during mapping maintenance while the GPU
idles. That is stage 1 of `DESIGN-device-mutex.md` with the chain mutex; this run raises its worth for the play
phase from "a quarter of the gaps" to "the long frames of play".

**Build note.** The ubuntu container's `linux-libc-dev` went from its earlier version to 7.0.0-43 at 18:13 (apt,
with perf). Before any A/B across that moment: build an untouched unit and compare its object's md5 with the object
of the last build before it (g412m, 18:08, is the last build made before the change).

### 26. The ordinary play frame: does the host hand the title's buffers to the kernel late? (run y1buf, 2026-11-11 18:42–18:46, the top session's order A)

**Hypothesis under test** (the top session's): the host's submission policy (chains, the ring thread's queue, the
device mutex) holds the title's buffers and gives them to the kernel late, so the GPU starts late and the labels
the title waits for come back late.

**Catcher.** `BC5_GUARD_BUF_STAT=<file>` (`memfast/buf0412.inc`, `memfast/mkbuf0412.py`, tag bf412; default off, no
behaviour change): one line when the title hands a buffer to `submit_split`, one per submission (its chain opened,
flushed, the reason of the flush), one when the completion thread sees its fence, one per label wait with the label's
address, one when the title calls the flip and one when the flip's drain ends; all on the journal's clock.
Build g412n = g412m + this, binary `9293fc81` (g412m kept). `buf0412.py` makes the tables; output
`raw/y1buf-buf-tables.txt`; the 30 MB line file stays on the box (`night/raw/y1buf-buf.txt`).
Run y1buf: arm fast2, RT on, watchdog 220 MiB (measuring run), scripted load; 181 s, 25.6 flips/s, a play phase of
49 s with 1,156 flips, 173,030 buffers handed, 41,636 submissions; lowest available 303 MiB; no kernel line.

**1. The host's queue** (chain opened to flushed, play phase) [M]:

| thread, kind, what flushed the chain | submissions/s | segments | opened -> flushed: median / p90 / max |
|---|---|---|---|
| `bc5-ring`, compute, end of the call | 327 | 3.5 | 0.01 / 0.09 / 16 ms |
| `bc5-ring`, compute, a wait | 213 | 3.8 | 0.01 / 0.07 / 1.5 ms |
| Render Thread, draw, a wait | 133 | 5.3 | 0.71 / 1.85 / 121 ms |
| `bc5-ring`, compute, reason 6 | 103 | 1.0 | 0.00 / 0.01 / 0.9 ms |
| Render Thread, draw, reason 10 | 35 | 15.4 | 2.09 / 2.40 / 12.5 ms |
| Render Thread, draw, the flip | 24 | 6.8 | 0.41 / 0.51 / 1.9 ms |
| `bc5-chainwd`, draw, the chain watchdog | 23 | 13.6 | 2.06 / 2.08 / 66 ms |

A buffer handed by the Render Thread reaches a flush in a median of 0.87 ms (p90 3.5 ms, p99 29 ms); one handed by
the ring thread in 0.01 ms (p99 0.3 ms). From the flush to the fence: median 3.1–3.9 ms, p90 6.5–12 ms.

**2. The time line of an ordinary frame** (704 frames of 33–50 ms; medians, ms from the end of the previous flip) [M]:
frame 34.1 ms; 148 buffers handed in 36 submissions; the first buffer handed at 0.1 ms and the first flush at 1.7 ms;
the last buffer and the last flush at 23.4 ms; **the title calls the flip at 22.4 ms; the last fence comes at
33.5 ms; the flip returns at 34.1 ms**. Share of the frame's command words flushed in each tenth of the frame:
4, 18, 10, 18, 12, 17, 11, 6, 2, 0 %. Time with nothing flushed-and-not-yet-fenced: 1.7 ms before the first flush,
1.3 ms between submissions, 0.7 ms after the last fence: 3.7 ms of 34.1.

**3. The label waits** [M]: 1,669 waits, all on the Render Thread, 5.5 s = 11.3 % of the phase, median 3.0 ms, p90
4.6 ms, on 10 labels (three hold 92 % of the time). For 47 % of the wait time the submission whose fence ended the
wait had been flushed before the wait began; for 52 % it was flushed after the wait began, a median of 0.25 ms (p90
0.55 ms) into a 3 ms wait. So the waits are the GPU working through what it already has, not buffers held back.

**Verdict: the hypothesis is not confirmed.** The host passes buffers on within a millisecond, submissions are
spread over the first two thirds of the frame as the title makes them, and something is in flight on the GPU for
30.4 of the 34.1 ms. The title has finished its frame's CPU work at 22.4 ms and then waits 11.7 ms for the GPU to
finish. **In the ordinary play frame the GPU side is the long pole**: its work for one frame takes about as long as
the frame. This corrects section 25's reading ("the CPU part and the GPU part one after the other"): they do
overlap for 22 ms; the GPU simply needs 30. "In flight" is from the host's flush to the fence, so it holds the
host's own submit work per submission (0.3–1 ms, section 21), the kernel's scheduling and the GPU's run; which of
the three is how much of the 30 ms this catcher cannot say. The GPU's clock in play is not readable here
(`pp_dpm_sclk` prints 9–100 "MHz" against a table of 1,000 and 2,000) [M, a non-result].

**The title's two wait loops, read from the running process (described only; nothing of the title is kept).** The
Render Thread's loop (section 25) is: while a state word in the title's own data is 1, call a helper of the title's
job system and, when it reports nothing to do, execute twenty `pause` instructions and look again; when the word
changes, the loop ends and the thread itself sets the word to 3. The main thread's loop compares two counters of a
job record. Both poll memory that only the title's own code writes: neither polls a label, a flip status or
anything the host updates. They are the title's threads waiting for its own jobs (its worker threads) and for
each other. What the workers are held by in the long frames is the next thing to name.

**What follows** [I]. For the ordinary frame the lever is on the GPU side of the submission: the number and size of
the submissions (36 a frame, each with its own state prefix, sync and fence round trip), the host's per-submission
work that sits inside "in flight", and whatever makes the GPU's own run long with RT on. A flush policy would not
help: nothing waits to be flushed. The 8 ms of host submission on the Render Thread (section 25) are inside the
22 ms the title needs anyway and do not set the frame's length while the GPU is the long pole.

**Build note.** g412n is the first build after the container's `linux-libc-dev` change. The object of the unchanged
unit `memory.cpp` differs from g412m's (`f6bb431a` against `9a518979`), but the two were compiled from different
directories (`.../n/out/...` and `.../m/out/...`), so the comparison says nothing yet; a rebuild of g412m's unit in
its own directory is the valid check and is not done.

### 27. What the long holds of the play phase are, and how the GPU is clocked (read from existing data, 2026-11-11 19:05, the top session's order)

**The long holds, from the journal of run r1holds** (section 22: arm fast2, a line per hold of 30 ms or more with its
parts; play phase 132–181 s; the journal is `~/bc5-data/captures/play-20261111-1752/gc/direct.log` on the box) [M]:

| hold of the device mutex, largest part | holds | time | what was journaled just before it |
|---|---|---|---|
| 100 ms and more, direct sync | 4 | 1.65 s | 1 right after a lazy-release cut (600 ms), 2 after it with nothing between (936 ms), 1 after a views rebuild (115 ms) |
| 100 ms and more, anon sync | 1 | 0.26 s | after a views rebuild |
| 30–100 ms, anon sync | 58 | 2.75 s | 34 after a views rebuild, 2 after a release cut, 22 with neither |
| 30–100 ms, direct sync | 15 | 0.56 s | 9 after a views rebuild, 4 after a release cut, 2 with neither |

- The worst cluster of the phase: the lazy release cuts 20 MiB out of 4 BOs ("43 mappings to move"), and the next
  four holds are direct sync on three threads, 594 ms (Render Thread), 101 ms (`bc5-ring`), 212 ms and 647 ms
  (`bc5-chainwd`), 1.55 s of holds within 1.5 s of wall clock. **So yes: the orphan release (exp 0401 e7's cut with
  this experiment's `BC5_GUARD_SPLIT`) runs inside the device mutex and starts the longest frames of the play phase.**
  The learned windows are not it (3–10 ms per hold here).
- Why the release has so much to do: over that run it cut 1,422 MiB and nearly all of it came back under views
  (section 18: 1,548 cut, 1,486 back). The title's AMM heap swings between about 2,485 and 2,965 MiB every 10 s; with
  `BC5_DIRECT_LAZY_RELEASE=4` a part freed for 4 s is cut out of its BO, and when the title maps it again some
  seconds later it is imported and its mappings rebuilt, each time under the mutex. The release works against a heap
  that breathes faster than it waits.
- The second kind, anon sync (59 holds, 3.0 s, 40–65 ms each, one of 239 ms): the forced walk over the guest's VMAs
  in `sync_mappings`, mostly right after the title changed its layout (a views rebuild).

**Proposal for order B** [I], cheaper than moving work out of the mutex and to be reviewed before any build:
1. Stop the churn at its source: a chunk that came back under a view after a cut is not cut again for a long time
   (minutes), or the idle time before a cut is longer than the heap's swing (30 s instead of 4 s). Cost: the release
   then saves little on this route (cut minus back was 62 MiB), so the pin goes back toward the ledger arm's
   12.0 GiB at the wall; the memory budget and the long frames pull in opposite directions here and the choice is
   the maintainer's.
2. For what is left (a real new mapping): do the import at map time on the mapping thread, outside the device
   mutex, and splice under it (stage 1 of `DESIGN-device-mutex.md` in its smallest form).
3. The anon sync walk: 23,000 mappings walked whole after every layout change; walking only the changed range is
   the same class of fix as sections 15 and 18.

**The GPU's clock and CUs** (read-only) [M]: `cyan-skillfish-governor-smu.service` is active, set by SMU, with
`/etc/cyan-skillfish-governor-smu/config.toml` `[frequency-range] min = 1850, max = 2150` MHz (the D-Bus object
`com.cyanskillfish.Governor` gives the same range; an older `config.toml.bak` had 1,000–1,850), load target
0.50–0.65, throttling at 85 C. `oberon-governor.service` and the other two governor units are not running. The
frequency the governor has set at a given moment is not exposed: hwmon `freq1_input` reads 9–60 MHz and
`pp_dpm_sclk` is no better. `bc250-cu-live-manager status`: 40/40 CUs active and routed; vddgfx 918–924 mV, 52 C and
64–69 W at idle. A console runs this GPU family at 2,230 MHz with 36 CUs; here it is 1,850–2,150 MHz with 40, so the
clock is 83–96 % of a console's and the CU count 111 %: the GPU is not clocked far below a console. Whether the
governor actually sits at 2,150 MHz in play is the one thing not read.

### 28. The return-aware release (fast3), and the maintainer's 30 s idle time, against fast2 (2026-11-11 18:55–19:13)

**What was built.** `BC5_GUARD_RETURN_EXEMPT=<s>` (`memfast/ret0412.inc`, `memfast/mkret0412.py`, tag ra412; default
off): a chunk that the lazy release cut and that came back under a view is not cut again for <s> seconds, doubling
with every further return (at most 64 times); a chunk that never came back keeps the release's own idle time. One
journal line every 10 s with cut, returned, exempt and net MiB. CPU test `memfast/ret0412.cpp`, old against new on a
model of the release's decision: 1,537 of 1,537 on the laptop and on the box. Build g412o = g412n + this, binary
`09c2d29b` (g412n kept). Arm **fast3** = fast2's words + `BC5_GUARD_RETURN_EXEMPT=300`.
On the maintainer's word of 19:10 ("Tak, 30 s") arm **fast2 now has `BC5_DIRECT_LAZY_RELEASE=30,eager`** (was 4);
the ABBA below ran before that change, with fast2 at 4 s.

**Runs** (`ab0412q.sh`: a1f2, a2f3, a3f3, a4f2; then b1s30 = fast2 with 30 s; scripted load, RT on, build g412o,
`BC5_GUARD_LOCK_STAT=1`, measuring watchdog 220 MiB; all five reached 176–178 s; no kernel line; `abq0412.py`,
data `raw/a?f?-*`, `raw/b1s30-*`) [M]:

| | fast2, 4 s (a1, a4) | fast3, return-aware (a2, a3) | fast2, 30 s (b1s30) |
|---|---|---|---|
| flips/s: scene load | 21.6 / 22.7 | 22.4 / 24.3 | 23.9 |
| flips/s: save load | 18.0 / 18.0 | 18.9 / 18.9 | 18.4 |
| flips/s: play | 21.6 / 20.8 | 20.4 / 22.0 | 21.4 |
| play: frames over 100 ms, count and time | 21, 4.5 s / 21, 5.7 s | 34, 6.8 s / 23, 5.1 s | 17, 4.7 s |
| play: frames over 50 ms, time | 17.0 / 16.9 s | 19.2 / 14.5 s | 15.8 s |
| play: holds of 30 ms and more | 82, 5.3 s / 81, 5.5 s | 81, 5.4 s / 68, 4.4 s | 67, 4.3 s |
| play: holds of 100 ms and more | 9, 1.8 s / 7, 2.0 s | 9, 1.9 s / 3, 1.3 s | 3, 1.2 s |
| pinned at 140 s (available) | 11,652 (292) / 11,632 (270) | 11,702 (299) / 11,682 (245) | 11,646 (302) |
| pinned at 170 s (available) | 11,584 (387) / 11,590 (320) | 11,588 (352) / 11,596 (313) | 11,598 (289) |
| the release: cut / returned over the run | 1,338 / 1,332 and 1,344 / 1,344 MiB | 1,518 / 1,396 and 1,522 / 1,408 MiB | 0 / 0 MiB |

**Reading.**
- fast3 is not better than fast2 on anything measured here and not worse on the wall. In a run of 180 s nearly every
  chunk the release cuts is cut for the first time, comes back once and only then becomes exempt, so the rule has
  nothing to prevent yet; its effect, if any, is in a longer play. Not shown by this ABBA.
- With a 30 s idle time the release cut nothing at all in the whole run, **and the pin is the same** (11,646 and
  11,598 MiB against 11,632–11,702 and 11,584–11,596). So on this route the release at 4 s does not lower the pin at
  the moments that matter: what it cuts is back before the wall. Section 18's "pin 11.5–11.65 against the ledger
  arm's 12.0 GiB" was therefore not the release's doing; the ledger arm of that hour differed in something else
  (not found; the comparison there was between runs of different hours).
- With no cut at all the long frames are still there: 17 frames over 100 ms (4.7 s) against 21–34 (4.5–6.8 s), holds
  of 30 ms and more 4.3 s against 4.4–5.5 s. **So the release starts one of the worst clusters (section 27) but is
  not the main source of the long frames; section 27's emphasis was too strong.** The differences between the three
  arms are inside the spread between two runs of one arm.
- The frames over 100 ms take 4.5–6.8 s of the play phase while the holds of 100 ms and more take 1.2–2.0 s: most
  of a long frame is made of many shorter holds and waits, which this hold catcher (30 ms and up) does not list.

**The 600 ms hold of section 27, looked at again** [M from the journal, the cause I]: in that hold the direct sync
imported one BO of 18 MiB and changed two mappings; nothing else. So the time was the import itself, pinning 18 MiB
whose pages the kernel had meanwhile evicted, on a box with 250–300 MiB available and `kcompactd0` at 30 % of a
CPU. It is kernel time for memory under pressure, not host bookkeeping that grows with the total. A delta-only
rewrite of the direct sync would not shorten it.

**The anon sync holds** (58 of the 30–100 ms holds in section 27) are `sync_mappings` reading and parsing
`/proc/self/maps`, about 28,000 lines through `std::getline` and `sscanf`, 40–65 ms each time under the device mutex
(`__vfscanf_internal` shows in section 24's profile). A hand-written parser of the same lines is a behaviour-neutral
fix with an old-against-new test on a recorded maps text; not built yet.

**Shortcut.** Unchanged: "BC5 emulator (0412 fast2)", which now runs with the 30 s idle time. fast3 is an arm of the
wrapper only (`play-guard-0412.sh fast3`); it gave no reason to replace the shortcut.

### 29. The maintainer's play of 2026-11-11 19:40–19:43 on fast2 (30 s) with the catchers on

He started "BC5 emulator (0412 fast2)" (build g412o, `BC5_DIRECT_LAZY_RELEASE=30,eager`), with
`catchers.env` = `BC5_GUARD_GAP_STAT=100`, `BC5_GUARD_LOCK_STAT=1` and the 20 ms sampler, loaded his save and gave up
inside three minutes: "Nie da się 5 minut ... nie da się przejść nawet in-game". The emulator ended with exit 0 at
19:43:38 (he closed it); no kernel line of that time. Data `raw/h2play-*` (journal lines, frames, the 5 s sampler);
the catchers were switched off again after the play (`catchers.env.off`).

**What happened** [M]: the memory wall, inside two minutes.

| seconds after the start | available MiB | swap used MiB | emulator major faults/s | PSI memory full | emulator CPU % |
|---|---|---|---|---|---|
| 62 | 3,662 | 594 | 0 | 0.0 % | 211 |
| 83 | 673 | 599 | 14 | 1.7 % | 457 |
| 98 | 609 | 599 | 0 | 3.2 % | 341 |
| 103 | 530 | 733 | 711 | 11.5 % | 606 |
| 119 | 321 | 870 | 2,035 | 19.2 % | 508 |
| 129 | 275 | 908 | 5,459 | 26.3 % | 613 |
| 145 | 250 | 943 | 6,159 | 30.7 % | 468 |
| 161 | 229 | 1,010 | 4,360 | 47.8 % | 871 |

The ledger: pinned 11,840 MiB at 121 s, 11,876 at 131 s, 11,892 at 141 s (orphans 281–342 MiB; views 28,684 over
12,195 MiB). Frames: 1,813 in all; 145 over 100 ms = 71.6 s; twelve over one second = 40.0 s: 3.1 s at 99 s, then
1.3–2.5 s each several times, 5.2 s at 129 s, and **15.3 s at 144 s, the last flip of the run**; the emulator then
stood for 30 s until he closed it.

**Reading.** From 103 s the box swaps: 2,000–6,000 major faults a second in the emulator, half the time stalled on
memory. This is the wall of section 16 reached on his live save, which pins about 250 MiB more than the copy of his
save the scripted runs load (11,840–11,892 against 11,580–11,700 MiB at the same seconds). The scripted runs sit
just above the watchdog's line; his play goes past it, and the shortcut has no watchdog, only the cgroup fuse at
12,400 MiB, which a thrashing emulator does not reach.
The catchers: the 20 ms sampler holds about 45 MiB and the journal lines are small. Against a deficit of several
hundred MiB they did not make this play fail, but they did not help either, and with no margin at all 45 MiB is
not nothing [I]. They are off again.
The 30 s idle time: in this play the orphans stayed at 281–342 MiB, which the 4 s setting would have cut at least
once. Whether that would have kept the play alive is not known from one play.

**What this means for the order of work.** Nothing measured in sections 19–28 (mutex holds, the submit path, the
release's timing) matters to his play while it ends like this: the first defect in his way is the 0.4–0.5 GiB of
memory that the box does not have (section 16). The levers that exist, none of them built or changed here:
the zero skip (0.6–0.75 GiB less pinned, with 2 GPU ring timeouts in 8 runs so far); a session without the Plasma
desktop while playing (the desktop's processes and its 285 MiB of GPU memory); a hard stop that ends the emulator
cleanly at the wall instead of letting it thrash (the watchdog of the scripted runs, for the shortcut).

### 30. The hard stop for shortcut plays, the save copy checked, and the lean session prepared (2026-11-11 19:46–19:55, the top session's order)

**The hard stop** (`stop0412.sh`, started by `play-guard-0412.sh` for every real play; `BC5_0412_STOP=0` turns it
off): every 2 s it reads MemAvailable and the memory pressure "full" avg10 with the shell's own `read`; after five
samples in a row (10 s) with less than 300 MiB available and 20 % or more pressure, or with 35 % pressure alone, it
ends the emulator (SIGTERM, SIGKILL 3 s later if needed), writes a line to `~/bc5-work/exp0412/stop.log` and opens a
window "BC5: zatrzymano, brak pamięci (N MiB)". The thresholds come from section 29: his play had 267–275 MiB and
23–26 % at 124–129 s, when the frames were already 2 s long; the scripted runs that live dip under 300 MiB with
3–20 % and recover. Tested on stand-ins on the box [M]: a `sleep` watched with thresholds that are true was ended
after five samples (about 10 s); one watched with thresholds that are false was left alone and its end noted. The
first version read the pressure line wrongly (it took `avg60` for the number) and never stopped anything; the
stand-in test caught that before any play. **Not tested:** the window itself (the stand-ins ran with
`STOP0412_QUIET=1`, so that nothing popped up on his desktop), and a real emulator at the wall.

**The save copy** [M]: the scripted runs' snapshot was made again from his current `~/bc5-work/_SaveData/PPSA03671`
(the old one kept as `night/saves-named.20261110`): the same content sum `1151e79071c72b17`, and `diff -r` finds
no difference; only the prefs file's time is newer. **So his live save and the copy are the same; the 250 MiB more
that his play pinned (section 29) is not the save.** What differs is what happens after the load: the script
walks forward for 60 s, he plays. No scripted run reproduces 11.84–11.89 GiB yet.

**The lean session, prepared, nothing stopped yet.** `lean0412.sh` and a hook in the wrapper (`BC5_0412_LEAN=1`):
before the emulator starts, `plasma-plasmashell.service` is stopped (now 169 MiB of memory in its cgroup, and
174 MiB of GPU memory by section 18); a watcher outside the launcher's process group starts it again when the
launcher's process is gone, whatever ended it. `plasma-keyboard` (19 MiB and 96 MiB of GPU memory) is a child of
KWin, not a unit of its own; stopping it needs a KWin setting and is left out. KWin, PipeWire, the pad's path, sshd
and tailscale are not touched. Only the dry print has run. The real stop-and-restore test and the measurement need
the desktop shell to disappear for some minutes on his running session, so they wait for his word.

**A correction to section 29.** The "about 45 MiB" given there for the 20 ms sampler was read off the process list
by mistake: that `python3` is `bc5-gpu-stall-sampler`, a service that has been running since boot. The sampler's
own size was not measured; it is a small Python process, and the play's failure does not hang on it.

### 31. Design note: zero pages without the GPU hang (2026-11-11 20:05; nothing built)

**The maintainer's point** (20:02): "Przecież ps5 się nie wysypuje gdy gra potrzebuję pamięci ... Problemem jest NASZ
kod i nasze biblioteki." What of the wall is ours, from this experiment's own numbers:
- We pin every page of the title's heaps the moment a view covers it, written or not. The two large GPU heaps
  (`RenderGpuWcLarge` 2,758 MiB, `CommitIABufferAllocator` 2,736 MiB) are about half all-zero, 1.38 GiB each
  ([M], the table of section 1; F394, F402, F540). A console backs its guest memory with its own page tables and
  need not pin anything for the GPU; our direct path pins because a GPU access to an unpinned page here is a fault
  that can take the machine down (F6). The pin of never-written pages is the largest single cost of that choice.
- Orphans, 180–340 MiB at the wall: memory under no view that we keep pinned (sections 16, 29).
- The host around the guest: the emulator's own memory, the mount process, the page tables for 28,000 mappings
  (section 16's table).

**What exists.** The zero skip (exp 0379, arm zo here) already does not pin the chunks of a scanned zero list, and it
already keeps the GPU from faulting: every skipped chunk is GPU-mapped onto a slice of one small "canary" BO at every
address a view gives it. It saved 0.6–0.75 GiB here. Its two ways of learning that a skipped chunk is no longer
zero: the canary slice is found changed (the GPU wrote there), and **the CPU's writes are found by polling the
memfd with SEEK_DATA at the next sync** (`zskip_take_back`), which runs at most every 50 ms unless the guest's ranges
changed (`direct_sync_one`).

**The suspected defect** [I, to be proven]: between the title's first CPU write into a skipped chunk and the next
sync that polls, the GPU still reads the canary's zeros at that address. If what the title wrote is something a
shader walks (an acceleration structure for the reflections, an index or argument table), a job submitted in that
window runs on zeros: a traversal that never ends is a ring timeout with no page fault line, which is exactly what
both timeouts looked like (c1zof at 99 s on the save list; his play at 09:54:16: "no page fault line, the ring reset
succeeded", sections 9 and 14). Ten runs without the zero skip had none.

**The fix to build: catch the first CPU write synchronously.** A skipped chunk's CPU pages are write-protected; the
first write faults; the handler pins the real chunk, swaps the GPU mappings from the canary to it, and only then
lets the write go on. No window is left in which the CPU has data and the GPU sees zeros. Two ways to get the fault:
- userfaultfd in write-protect mode on the memfd's mappings: supported for shmem on this kernel (7.2.15);
  `vm.unprivileged_userfaultfd` is 0 here, which still allows a descriptor made with `UFFD_USER_MODE_ONLY`, and the
  title's writes are user-mode. The host's own writes into guest memory (read() into a guest buffer, memcpy in a
  library call) would fault in the kernel and are refused in that mode: they need the chunk taken back before the
  call, or the second way.
- `mprotect` to read-only and the host's existing SIGSEGV path (the one the learned windows use): no new kernel
  feature, catches both kinds of write, but a guest thread inside a host library call must be handled the same way.
Chunks the GPU may write (render targets and compute outputs, known from the hints and learned windows) are never
skipped: that rule exists already (`direct_force` takes a skipped chunk back).

**What makes it feasible in our code:** the canary mapping, the take-back and the swap of mappings exist and are
tested (exp 0379's CPU tests); what is new is the trigger (a fault instead of a poll) and doing the take-back on the
faulting thread under the device mutex. **What can make it fail:** a write from kernel context into a protected
page; the cost of a fault per 2 MiB chunk at the moment the title starts using a region (one fault per chunk, then
never again); 28,000 mappings to protect and unprotect.

**Expected on his save:** the list scanned at his save holds what gave 0.6–0.75 GiB in the night's runs; the heaps'
all-zero halves are 2.8 GiB, and the list could be dropped for "skip whatever the title has not written" once the
write is caught synchronously, since then nothing depends on a scan made earlier. That is more than the 0.4–0.5 GiB
the wall lacks.

**Order of proof before any play:** (1) a catcher in the existing zero skip that journals, for every chunk taken
back by the poll, how long the CPU's data had been there unseen and whether a submission ran in between (it proves
or kills the suspected defect with the build we have); (2) the fault trigger behind its own switch with exp 0379's
CPU tests extended; (3) scripted runs with the zero skip and the trigger, counting ring timeouts against the 2 in 8.

### 32. How much of the pinned memory do command buffers name? (build g412p, 2026-11-11 19:57–19:59; a first, cut-short answer)

**Question** (the top session's frame): we pin every byte the GPU could address; how much does the GPU touch? If
little, residency could follow use.

**Catcher.** `BC5_GUARD_USE_STAT=1` (`memfast/use0412.inc`, `memfast/mkuse0412.py`, tag us412; default off, no
behaviour change): every memory operand the backend's filter asks about at submission stamps its 2 MiB chunks of
guest address space; every 30 s the direct sync prints, per heap name, the MiB under views and of them the MiB in
chunks an operand named ever / in the last 60 s / 10 s / 1 s. Build g412p = g412o + this, binary `e4dfc6d6` (g412o
kept).

**The run, c1use, is not a valid measuring run.** The watchdog ended it at 90 s on pressure (PSI full 66 %), before
the save list. Cause [M]: Steam was running on the box (four `steamwebhelper` processes of 58–202 MiB and `steam`;
available 2,400 MiB at 26 s where every earlier run had 3,900–4,100, swap 1,092 MiB used at the start). Steam was not
started by this session; the guard before a run looks for an emulator and the lock only. No further run is made
while Steam is up.

**What the two tables that were printed say** (30 s and 60 s after the start, the title's menus) [M]:

| | under views | in chunks an operand named: ever | last 10 s |
|---|---|---|---|
| direct memory, all heaps (30 s) | 9,619 MiB | 44 MiB (23 chunks) | 36 MiB |
| `RenderGpuWcLarge` | 2,758 | 6 | 4 |
| `CommitIABufferAllocator` | 2,736 | 0 | 0 |
| `RenderGpuRwLarge` | 414 | 28 | 22 |
| `AssetHeap Large`, `InitAllocator`, `AMM`, the others | 3,700 | 0 | 0 |
| private memory (60 s) | 346 | 2 | 2 |

after 921,650 operands (2.7 million by 60 s).

**Reading.** In the menus the command buffers name 0.5 % of the memory under views, and of the heap that is
certainly drawn from (`CommitIABufferAllocator`: index and vertex buffers by its name [I]) not one chunk. The
addresses of what the shaders read are not in the command stream: the buffers carry register values and a few
tables, and the shaders reach textures and buffers through descriptors and pointers they load from memory. That is
the limit written into the catcher, and it is the whole picture, not a detail. **So the host cannot learn the GPU's
use of memory from the command buffers, and a residency scheme driven by "what the next submission references"
has nothing to stand on.** The play phase was not reached; nothing suggests it differs in kind.

**What does carry information about use** [I]: the title's own calls (what it maps, unmaps, commits and gives a
type to), the CPU's first write to a page (the zero pages of section 31: memory the title has reserved and never
filled), and the GPU's own faults, which this driver turns into a hang instead of a recoverable event. Section 31's
scheme uses the second. The first is the subject of the library review the maintainer ordered (a sub-agent of this
session; its note goes to the shared notes folder).

**Not done from the top session's list.** The kernel's rule for what holds the pages (udmabuf create against the BO
list of a submission): the public source could not be fetched (the host rate-limited all three files), so it is not
cited here; what this experiment measured itself is that the pin follows the imports, not the submissions (the
ledger's "pinned" is the sum of imported BOs, section 7). The class split at 130 s on his save needs a valid run.

### 33. The zero skip's blind window, caught with a GPU hang beside it (build g412q, run d1zc, 2026-11-11 20:03–20:06, on the maintainer's "Zbuduj łapacz")

**Catcher.** `BC5_GUARD_ZSKIP_STAT=1` (`memfast/zcat0412.inc`, `memfast/mkzcat0412.py`, tag zc412; default off, no
behaviour change): every time the zero skip's poll (`zskip_take_back`, SEEK_DATA on the memfd) finds CPU data in a
chunk it had left unpinned, one journal line says how long ago the previous poll was (the title wrote the data
inside that time, while the GPU had the canary's zeros mapped there) and how many submissions went to the GPU in
between. Build g412q = g412p + this, binary `f344f790` (g412p kept).

**Run d1zc**: arm zo (zero skip with the list scanned at his save + orphan release + split) with both table fixes,
scripted load, RT on, measuring watchdog 220 MiB, Steam not running. **It ended in a GPU hang: gfx ring timeout,
thread `bc5-chainwd`, no page fault line, the ring reset succeeded, the box stayed up** (the third such timeout
with the zero skip, in 9 runs now). Data `raw/d1zc-*`.

**Result** [M]:
- 1,010 MiB placed as skipped (740 MiB of `RenderGpuWcLarge` in 30 runs, 270 MiB of `CommitIABufferAllocator` in 3).
- In the first 90 s the poll found 45 chunks written by the CPU; for 45 of them submissions had gone out since the
  previous poll, 1,204 submissions in all. The window: mean 58.8 ms, longest 149 ms, over 10 ms for 40 chunks,
  over 50 ms for 19. (Corrected 2026-11-12 after the review, R13: these are intervals BETWEEN TWO SCANS and the
  submissions counted in them. When inside an interval the CPU wrote is not known, so it is not known how many
  of those submissions went out after the write; and the catcher does not tie any submission to a read of the
  chunk or to the values read.)
- The hang: the last good flip is at 99.503 s. **At 99.507 s the poll found CPU data in the chunk at file offset
  0x22e200000, which lies in the skipped part of `CommitIABufferAllocator`; the previous poll was 31.7 ms earlier
  and 15 submissions had gone out in between.** A second chunk followed at 99.609 s (22.8 ms, no submission).
  The next frame never completed: it lasted 17.1 s, and the kernel logged the ring timeout for a job of that frame.
  No chunk was found between 83.0 s and 99.5 s.

**Reading.** The blind window is real and long: tens of milliseconds, with tens of submissions inside it. And the
one hang of this run starts within 4 ms of a scan that found CPU data in a skipped chunk of the index-and-vertex
heap, 31.7 ms and 15 submissions after the scan before it. That is nearness in time and in place, both measured.
That the write came before any of those 15 submissions, that one of them read that chunk, and that zeros there
make a job that never ends are each inferred [I]: "the GPU read zeros" is a hypothesis (corrected 2026-11-12, R13). It is the mechanism of section 31, now with a measured case; the two earlier timeouts
(sections 9, 14) had the same signature and no catcher.
The polls themselves are not rare (1,946 in 90 s, 22 a second); the window is long because a poll happens only at
a sync, and syncs are throttled and skipped for light buffers. Polling more often narrows the window and cannot
close it: the write and the submission are on different threads.

**What follows.** The synchronous catch of the first CPU write (section 31) is the fix to build: with it there is
no moment in which the title's data exists and the GPU sees zeros. Until then the zero skip stays out of his
shortcuts. The catcher stays in the build for the proof run of the fix: the count of chunks found by the poll must
then be zero.

### 34. What command buffers name of the pinned memory, the valid run (c2use, 2026-11-11 20:08–20:11)

Section 32's question again on a clean box (Steam closed by the maintainer; 12.9 GiB available at the start): arm
fast2, build g412q, `BC5_GUARD_USE_STAT=1`, scripted load, measuring watchdog 220 MiB. The run reached 181 s (46 s of
play), 23.6 flips/s, lowest available 233 MiB, no kernel line. Data `raw/c2use-usestat.txt`.

**Over the run** (direct memory; MiB in 2 MiB chunks that an operand of a submitted command buffer named) [M]:

| seconds | under views | named ever | last 60 s | last 10 s | last 1 s | operands so far |
|---|---|---|---|---|---|---|
| 30 (menus) | 9,619 | 44 | 44 | 36 | 36 | 1.0 million |
| 60 (scene load) | 12,078 | 450 | 450 | 450 | 148 | 3.6 million |
| 120 (save load) | 12,184 | 744 | 586 | 334 | 162 | 13.6 million |
| 150 (play) | 12,190 | 918 | 784 | 314 | 204 | 17.5 million |

**By heap at 150 s, in play** (pinned then: 11,680 MiB, of it 11,425 under a view and 255 orphans) [M]:

| heap | under views | named ever | last 60 s | last 10 s | last 1 s |
|---|---|---|---|---|---|
| `AMM` | 2,966 | 0 | 0 | 0 | 0 |
| `RenderGpuWcLarge` | 2,758 | 70 | 70 | 56 | 54 |
| `CommitIABufferAllocator` | 2,736 | 724 | 596 | 172 | 76 |
| `AssetHeap Large` | 816 | 0 | 0 | 0 | 0 |
| `InitAllocator` | 652 | 0 | 0 | 0 | 0 |
| `RenderGpuRwLarge` | 414 | 98 | 92 | 66 | 54 |
| `AssetHeap Small`, `DynamicHeap`, `Wwise`, `Physics`, `anon`, `ComponentHeap`, `RenderAlloc` | 1,430 | 0 | 0 | 0 | 0 |
| `RenderGpuWcSmall` | 110 | 14 | 14 | 8 | 8 |
| all | 12,190 | 918 | 784 | 314 | 204 |

**Reading.**
- Command buffers name 7.5 % of the memory under views by the play phase (918 MiB of 12,190), and 2.6 % in any
  10 s. What they name is where the name says: the index-and-vertex heap (724 MiB of its 2,736) and the two
  read-write render heaps.
- **Seven heaps, 5.9 GiB, are never named at all: `AMM` (2,966 MiB), the two asset heaps, `InitAllocator`,
  `DynamicHeap`, `Wwise`, `Physics`, `ComponentHeap`, `RenderAlloc`, `anon`.** `Wwise` is the audio engine's and
  `Physics` the physics engine's by their names; nothing suggests the GPU reads them at all [I]. `AMM` is the
  streaming pool: textures and geometry the shaders reach through descriptors, so "never named" there does NOT
  mean "not used by the GPU" (the limit written in section 32).
- So the catcher splits the pinned memory into three kinds, not two: named by commands (0.9 GiB), reachable only
  through shaders (the GPU heaps and `AMM`: the catcher is blind there), and heaps that by their purpose are the
  CPU's (`Wwise` 220, `Physics` 192, `ComponentHeap` 104 and probably `DynamicHeap` 328, `InitAllocator` 652,
  `AssetHeap` 1,166: up to 2.7 GiB) which we pin for the GPU only because the title mapped them as direct memory.

**What this adds to the plan** [I]. Besides the zero pages (section 31), a second defect of ours is now visible: we
pin for the GPU every direct-memory heap whether or not the title ever marked it for the GPU. The library review
(`ps5-libs-review.md` in the shared notes) reports that the title's GPU protection bits are decoded by the host and
never read by the mapper. If those bits, or the memory type the title gives a range, separate the CPU's heaps from
the GPU's, then up to 2.7 GiB need not be pinned at all, with no fault trap and no risk for the GPU, since the GPU
has no mapping there to miss. That is cheaper and safer than anything else on the table and has to be checked
first: which protection bits and memory types the seven never-named heaps carry on his save.

### 35. The title's own protection bits per heap (build g412r, run e1prot, 2026-11-11 20:14–20:18)

**Why.** Section 34 left heaps that no command buffer ever names; the library review reported that the host decodes
the title's GPU protection bits and the mapper never reads them. The check: which bits does each heap carry?

**Change** (`memfast/mkprot0412.py`, tag pr412; no behaviour change): `Bc5ForEachMappedRange` already hands the
view builder a protection value for every mapped range; `direct_views_build` took it as an unnamed, ignored
argument. It is now stored in the view (`DView::prot`) and printed by the use catcher per heap. Build g412r = g412q
+ this, binary `a5829b25` (g412q kept). Run e1prot: arm fast2, `BC5_GUARD_USE_STAT=1`, scripted load; 178 s,
25.1 flips/s, no kernel line. Data `raw/e1prot-usestat.txt`.

**Result at 150 s, in play** [M] (the value as the host hands it over; 0x10 and 0x20 are GPU read and GPU write by
the host's own comment "prot 0x22 = cpu write | gpu write" in the unit; the bits above 0x30 are not explained
anywhere I have read: TODO(verify)):

| heap | under views MiB | value | a GPU bit? | in the launcher's lists |
|---|---|---|---|---|
| `AMM` | 2,964 | 0x13 (2,417), 0x33 (444), 0x32 (103) | yes | eager |
| `RenderGpuWcLarge` | 2,758 | 0x32 | yes | eager |
| `CommitIABufferAllocator` | 2,736 | 0xf2 | yes | eager |
| `AssetHeap Large` / `Small` | 816 / 350 | 0xf2 | yes | by data |
| `RenderGpuRwLarge` | 414 | 0xf2 | yes | eager |
| `Wwise` | 220 | 0x3f2 | yes | lazy (exp 0330: CPU-only) |
| `anon` | 166 | 0xfffffff2 | (all bits set) | by data |
| `RenderGpuWcSmall`, `RenderAlloc` | 110, 70 | 0x32, 0xf2 | yes | eager |
| **`InitAllocator`** | 652 | 0xc2 | **no** | by data (448–450 pinned) |
| **`DynamicHeap`** | 328 | 0xc2 | **no** | eager (328 pinned) |
| **`Physics`** | 192 | 0xc2 | **no** | eager (192 pinned) |
| **`ComponentHeap`** | 104 | 0xc2 | **no** | eager (104 pinned) |
| all | 12,189 | | 10,667 with, **1,522 without** | |

**Reading, with its contradiction.** 1,522 MiB under views carry neither GPU bit, about 1.1 GiB of it pinned today,
and section 34 shows that no command buffer names any of those heaps. Two signs that this memory is the CPU's.
Against that stands an older measured fact: F96 (exp 0042) records that run 102 **stopped on a GPU fault inside
`Physics`**, which is why `Physics` and "eleven more heaps" were put on the eager list. And `Wwise`, which exp 0330
treats as CPU-only without trouble, carries GPU bits here. So the value as I read it does not by itself say "the
GPU never goes there": either the bits mean something else than the comment says, or the GPU reaches that memory
through another mapping of it, or F96's fault had another cause than a real use.
**So this is a lead worth about 1.1 GiB and not yet a fix.** What settles it without risking a hang: map the four
no-GPU-bit heaps for the GPU onto the zero canary instead of their pages (no fault is possible), leave them
unpinned, and watch for canary hits and for a picture that changes; `Physics` first and alone, because it is the
one with a recorded fault. Not built.

### 36. The same table on the maintainer's own load (play h3play, 2026-11-11 20:21–20:24)

He said the scripted runs did not load his save the way he does, so the second measurement was repeated with him
at the pad: the emulator started on his desktop through `play-guard-0412.sh fast2` (build g412r, `catchers.env` =
`BC5_GUARD_USE_STAT=1`, no script, no watchdog, the hard stop off), he loaded his save, and on his word the session
closed the emulator at 172 s (SIGTERM). The catcher is off again. Data `raw/h3play-usestat.txt`.

**Result** [M]:
- **The wall again.** Pinned 11,846–11,932 MiB from 111 s on (the scripted runs: 11,580–11,700), available 220–275
  MiB; 21 frames over one second from 98 s on, the longest 15.6 s at 129 s and 6.5 s at 142 s.
- **Where his 200–250 MiB more are:** the asset heaps hold more data on his load: `AssetHeap Large` 644 of 816 MiB
  pinned (scripted: 504) and `AssetHeap Small` 282 of 350 (scripted: 230), together +192 MiB; the orphans are
  272–355 MiB (scripted: 230–255). `InitAllocator` 414 (scripted: 448–450). The other heaps are the same.
  So his load brings in more assets than the script's (another slot or another place in the game than the one the
  script's first cross picks [I]); the save data itself is the same file set (section 30).
- **The protection bits are the same as in the scripted run:** 10,673 MiB with a GPU bit, 1,517 MiB with none:
  `InitAllocator` 652 (414 pinned), `DynamicHeap` 328, `Physics` 192, `ComponentHeap` 104 (pinned whole):
  1,038 MiB pinned without a GPU bit on his load.
- **Named by command buffers:** 788 MiB of 12,190 ever, the same heaps as in section 34; nothing in the four
  no-GPU-bit heaps, nothing in `AMM` or the asset heaps.

**Reading.** His load needs about 0.2–0.25 GiB more than the scripted route, so the scripted runs understate the
wall by that much; the pin without a GPU bit is 1.0 GiB on his load too, four times that difference and twice the
deficit of section 16. Section 35's contradiction (F96's fault inside `Physics`) stands and is what has to be
settled before that memory is left unpinned.

### 37. Heaps the title mapped without a GPU bit are not pinned (build g412s, 2026-11-11 20:27–20:50, the top session's order)

**The old fault, settled as far as the data goes.** F96's "fault inside `Physics`" is run 102 of exp 0042
(`experiments/0042-pkg-title-heap-import/series-100.txt`): one GPU fault at 0x12d0410000, 4.1 MiB into the heap, on
a day whose other stops were faults at addresses outside every heap ("wild addresses", runs 103, 109, 110, 112,
which went on after the eager list was extended). No protection value was logged then, so whether that range had a
GPU bit at that moment cannot be read back. One stray access among stray accesses is what it looks like [I]; the
trial below gives such an access zeros instead of a fault.

**The change** (`memfast/nogpu0412.inc`, `memfast/mknogpu0412.py`, tag ng412; default off):
`BC5_GUARD_NOGPU_UNPIN=<heap>[,<heap>...]`. A 2 MiB chunk of the direct file is not imported (not pinned) when every
view that touches it is of a listed heap and carries neither GPU bit (0x10, 0x20: `PROT_GPU_READ` /
`PROT_GPU_WRITE` in the host's memory layer). A chunk that a hint or a learned window forced, and one that another
view with a GPU bit touches, is imported as before. Under the views of what is left out the GPU gets the shared zero
buffer (the mechanism of the cap arm, `guard0412_want`), so an access there cannot fault; every 10 s the buffer is
read back and a GPU write into it is journaled.
The transition that must be exact: when the title gives such a range a GPU bit, the protection edit in
`VirtualRanges` bumps the guest ranges' generation (e8's `memory.cpp`, the edit at line 473 and the bump at 478;
all eight places that change the ranges bump it), the views are rebuilt, the chunk leaves the left-out set, and the
same sync imports and maps it before the next submission is handed to the kernel. It is "before the next
submission", not "before the call returns".
CPU test `memfast/nogpu0412.cpp`: the selection against a page-level model on 3,000 random layouts, 15,001 of
15,001 on the laptop and on the box (a view that gains a GPU bit has none of its chunks left out; a chunk shared
with a GPU view is imported). Build g412s = g412r + this, binary `ec8b4594` (g412r kept).

**Runs** (`ab0412s.sh`; arm fast2 on the scripted load, RT on, measuring watchdog 220 MiB; one run each; data
`raw/f?*-*`) [M]:

| run, heaps left unpinned | not pinned at the end | pinned at 150 s | lowest available | PSI full, highest | play: frames over 100 ms | flips/s scene / save / play |
|---|---|---|---|---|---|---|
| f0base, none | 0 | 11,704 MiB | 283 MiB | 11 % | 22, 3.7 s | 20.9 / 19.5 / 21.7 |
| f1phys, `Physics` | 96 MiB of 192 | 11,632 | 267 | 14 % | 19, 2.6 s | 20.6 / 17.2 / 22.3 |
| f2comp, `ComponentHeap` | 104 of 104 | 11,604 | 261 | 16 % | 16, 3.8 s | 23.3 / 17.5 / 22.1 |
| f3dyn, `DynamicHeap` | 328 of 328 | 11,364 | 368 | 8 % | 9, 2.0 s | 23.6 / 18.1 / 23.7 |
| f4init, `InitAllocator` | 652 of 652 (448 were pinned) | 11,216 | 306 | 11 % | 24, 3.0 s | 22.8 / 16.9 / 21.7 |
| **f5all, all four** | **1,180 MiB** | **10,680** | **428** | **4 %** | **14, 1.8 s** | 24.7 / 18.9 / 22.3 |

In all six: no kernel line, no GPU fault or timeout line in the journal, no failed import; the zero buffer read
back as all zeros every time (no GPU write into a left-out range). All reached 178–180 s.
`Physics`: half of it (96 MiB) stays pinned because learned windows force those chunks: the fault of run 102
taught the host a window there, and the rule keeps what is forced.

**Reading.** With the four heaps left out the pin at the wall is 1,024 MiB lower (10,680 against 11,704), the lowest
available memory of the run is 428 MiB instead of 283, the memory pressure a third, and the long frames of the
play phase half (one run each: the direction is clear, the sizes are one sample). That is twice the deficit of
section 16. **What these runs cannot show is the picture:** a GPU read from a left-out range returns zeros without
any sign in a log. Nobody has looked at the image of this arm. On his own load the pin is about 0.2 GiB higher
(section 36), so the margin there will be about 0.2 GiB less than here.

**Read-only GPU ranges** (the other direction of the bits, noted on the top session's word): `AMM` has 2,417–2,558
MiB with 0x13, GPU read without GPU write. Nothing to gain in memory; it says the GPU never writes there, which a
zero-page scheme can use (section 31: no canary write to expect in those ranges).

**The arm.** `play-guard-0412.sh fast4` = fast2 + `BC5_GUARD_NOGPU_UNPIN=Physics,ComponentHeap,DynamicHeap,InitAllocator`.
It is in the wrapper; the desktop shortcut is not changed (it needs the maintainer's word and his eyes on the image).

### 38. His play on fast4 ended in a GPU hang and a reboot of the box (2026-11-11 22:30–22:32)

The maintainer started "BC5 emulator (0412 fast4)" (build g412s `ec8b4594`, RT on, no catchers) at 22:30:35, loaded his
save and reported "Crash". Data: `~/bc5-data/captures/play-20261111-2230/gc/direct.log` (2.5 MB, on the box), the two
dumped command buffers beside it (`ib-timeout-00073252-acb-7541.bin`, `ib-timeout-00073248-dcb-2925.bin`; the title's
buffers, never committed), the panic record in `~/bc5-data/captures/pstore/dmesg-efi_pstore-1794432746*` [M]:

- 22:32:25, about 108 s into the run: `ring gfx_0.0.0 timeout`, thread `bc5-ring`. The host's own journal has two
  submissions timed out at 2.0 s: #73252, a compute buffer of 7,541 dwords with 269 dispatches (the largest grid
  61,440 groups, the last one, at dword 7400), and #73248, a draw buffer of 2,925 dwords.
- `Ring gfx_0.0.0 reset failed` 0.19 s later, the kernel began a full GPU reset, and `bc5-gpu-watch` crashed the
  kernel for a reboot as it is built to do (SysRq s, c). The box was back at 22:32:55. No devcoredump of this hang was
  saved (the newest file is of 20:05). Kernel in the panic record: 7.2.15-ogc1.1 (CLAUDE.md records 7.2.11).
- Memory at the last ledger line (t 100 s): pinned direct 11,048 MiB, available 337 MiB, PSI full 1.2 %, 1,180 MiB in
  590 chunks left unpinned by the trial. Not at the wall of his earlier plays (11.84–11.93 GiB, 220–275 MiB).
- The only zero-buffer read-back in the journal is the one at t 1 s (0 non-zero bytes); the 10 s readings of the
  scripted runs are not there. Why is not known yet.

**Reading [I].** The trial of section 37 is the only thing that differs from his three plays on fast2, none of which
had a ring timeout, so it is the first suspect: a GPU read from a left-out range returns zeros, and a shader that
walks a structure there (a traversal, a list) can loop for ever on zeros. That is not shown: the probe prints the
draw buffer's bindings, not the compute dispatches' buffers, and the journal does not list the addresses of the
left-out views. The six scripted runs of section 37 did not hit it; his load and his play did, once. One event.

**What it settles.** "No GPU bit in the title's protection" is not enough to conclude "the GPU never reads it", at
least not for all four heaps on his load. fast4 is not an arm for his shortcut as it stands.

**Next.** Decode the compute buffer's dispatch at dword 7400 and the draw buffer's bindings against the left-out
ranges (the trial has to journal those ranges; one line per change), then a per-heap repeat on his slot with the
scripted route (the slot is still to be asked).

### 39. The GPU's work does name the four "no GPU bit" heaps: section 37's rule is refuted (build g412t, 2026-11-11 22:50–23:10)

On the maintainer's "Znajdź rozwiązanie" after the hang of section 38.

**The catcher and the candidate fix in one build** (`memfast/nscan0412.inc`, `memfast/mknscan0412.py`, tag ns412; default
off): `BC5_GUARD_NOGPU_SCAN=1|2`. Before a command buffer is handed to the kernel it is searched by value for addresses
inside the ranges `BC5_GUARD_NOGPU_UNPIN` left unpinned, in the two forms the probe lines of the hang show (a dword
pair "low 32 bits, high bits in the low 16 of the next dword", and a dword that is the address shifted right by 8:
image descriptors); so are the first 2 KiB behind every address in the buffer that points into other direct memory
(up to 96 tables per buffer). Mode 1 journals a find; mode 2 also pins 8 MiB from the find on before the submission
(`direct_force`, the hints' own call). The left-out ranges are journaled per heap whenever the set changes.
CPU test `memfast/nscan0412.cpp`: 13,435 of 13,435 on the laptop and on the box (the ranges against a page model, the
search against a brute-force one). Build g412t = g412s + this, binary `5e26c97d` (g412s kept; `mk0412t.sh`).
Section 38's open point is closed by reading the code: the zero buffer's read-back prints only when its result
changes, so one line at t 1 s is what a clean run gives.

**Runs** (scripted load, arm fast4, RT on, measuring watchdog 220 MiB; one each) [M]:

| run | scan | buffers searched | with a find | left unpinned at the end | pinned direct at 170 s | lowest line: available |
|---|---|---|---|---|---|---|
| t1scan | 1 (journal) | 140,096 | **87,223 (62 %)** | 1,180 MiB | 10,640 MiB | 788 MiB |
| t2pin | 2 (pin) | 108,741 | 179 | **264 MiB** | **11,800 MiB** | 310 MiB |

- t1scan: 42,623 finds in the buffers themselves and 2.05 million through tables. In the journaled sample (8,510
  lines): `InitAllocator` 258 distinct addresses in 63 chunks, `DynamicHeap` 77 in 44, `ComponentHeap` 7 in 5,
  `Physics` 1. Among them image descriptors (the shifted form) with bases 0x1041200000, 0x1041240000, 0x1041280000 in
  `DynamicHeap` and 0x1071280000, 0x10712c0000 in `ComponentHeap`: 256 KiB apart, page-aligned: textures [I].
  Others are pointers inside tables in GPU heaps (0x11e0…, 0x1200…) to `InitAllocator`; some of those may be the
  title's own CPU pointers lying beside GPU data (the search is by value).
- t2pin: pinning what is named took back 1,114 MiB of the 1,180: the pin was at the wall again (11,800 MiB,
  available 310 MiB, PSI 15 %). The 8 MiB window overstates it; the direction does not change.
- The search cost 13.8 s of the submitting threads in 170 s (8 %): a catcher's price, not an arm's.
- Both runs: no kernel line, no timeout line, 178 s.

**Verdict on section 37.** The title's protection value without bits 0x10/0x20 does **not** mean "the GPU never reads
it": on this title the GPU's own command buffers and tables name `DynamicHeap`, `InitAllocator` and `ComponentHeap`.
Arm fast4 gained its 1.0 GiB by giving the GPU zeros where it reads the title's data. That is the cause of the hang
of section 38 as far as it can be shown without the hung dispatch's own bindings [I], and it would also have shown
as a wrong picture. **fast4 is withdrawn as an arm for play**; `BC5_GUARD_NOGPU_UNPIN` stays in the build, off.
(TODO(verify): what the value's bits above 0x30 mean; 0xc2 heaps are GPU-read in practice.)

**The number that points at a fix: all-zero pages** (`zero0412.py`, run u2zero: arm fast2, scripted load; the direct
memory file read from outside through `/proc/<pid>/fd` at 140 s, in play; `raw/u2zero-zero.txt`) [M]:
of 11,826 MiB allocated in the file (pinned direct 11,716 MiB at that time), **3,571 MiB are 4 KiB pages holding
only zeros (30 %)**. Each is a real page of RAM that exists only because the import pinned it or because something
wrote zeros. That is 3.5 times the deficit of section 16. What it does not say: how many of those pages the title or
the GPU will write later, and how many lie in wholly-zero 2 MiB chunks (the granularity the zero skip of exp 0379
works at; a per-chunk count is the next read). It sizes section 31's scheme: keep such pages unbacked and catch the
first write synchronously, instead of the zero skip's poll with its blind window (section 33).

**Box state.** g412t in place; the desktop still has "BC5 emulator (0412 fast4)" on the maintainer's word ("Nie
przywracaj"): it will hang again if started.

### 40. The zero skip polls before every submission: nine runs, no hang, 650 MiB less pinned (build g412u, 2026-11-11 23:20 – 11-12 00:19)

On the maintainer's "Tak, buduj" (the zero-page fix of sections 31 and 39).

**What was built instead of the write trap, and why.** Section 31 proposed catching the CPU's first write into a
skipped chunk with a page fault. Reading the code again showed a smaller change with the same guarantee for every
ordering the title can rely on, and without the trap's open ends (the title's own `mprotect` undoing ours; a kernel
write such as `read()` into a protected page failing with EFAULT): **the poll is moved to the one moment that
matters, the hand-over of each command buffer to the kernel.** Data that a buffer depends on was written before the
title submitted it; so if the host looks, under the device mutex and before it takes the mapping list for that
buffer, whether the direct file has grown, and takes the written chunk back and maps it before going on, the GPU
never runs a buffer on the canary's zeros where data exists. The look is one `fstat` (a write into a hole changes
the file's block count), and the SEEK_DATA walk runs only when it changed. Only a write racing a buffer that is
already with the kernel stays unseen until the next submission, and no title can depend on that order.
`BC5_GUARD_ZSKIP_POLL_SUBMIT=1` (`memfast/mkzpoll0412.py`, tag zp412; default off, one test of a constant).
It is glue around exp 0379's functions (`zskip_take_back`, `direct_sync_one`). (As built in g412u it had no CPU test
and a defect the review found; see section 45.) Build g412u = g412t + this, binary `1f39cd1e` (g412t kept;
`memfast/mk0412u.sh`).

**Arm fast5** = fast2 + `BC5_DIRECT_ZERO_SKIP=<the list scanned at his save, 1,010 MiB in 33 runs>` +
`BC5_GUARD_ZSKIP_POLL_SUBMIT=1`.

**Runs** (`ab0412u.sh`: fast5, scripted load, RT on, the zero skip's catcher on, measuring watchdog 220 MiB; nine
runs v1zp–v9zp, 23:49–00:19; `raw/ab0412u.out`, `raw/v?zp-zpoll.txt`) [M]:

| | fast2 (f0base, u2zero) | fast5, nine runs |
|---|---|---|
| gfx ring timeouts | 0 | **0 of 9** (the old zero skip: 3 of 9, sections 9, 14, 33) |
| pinned direct at 150 s | 11,704–11,716 MiB | **11,000–11,102 MiB** |
| lowest available memory of the run | 283–384 MiB | **680–889 MiB** |
| still skipped at the end | – | 642–702 MiB of 1,010 |
| flips/s over the run | 24.7–25.6 | 25.2–26.3 |
| longest gap | 550 ms (t1scan) | 568–829 ms |

- The look: about 140,000 per run, the file had grown at about 850 of them, **0 to 3 chunks per run were taken back
  at a submission**; 0.43–0.47 s spent in all per run (0.3 % of the run).
- The catcher of section 33 in v9zp: 0 chunks found by a sync's poll with a submission before it.
- All nine reached 178–180 s; no kernel line, no crash line.

**Reading, with its limits.** 0 timeouts in 9 runs here against 3 in 9 with the old zero skip (a one-sided exact
Fisher test on those counts gives 0.103, and the two series are not the same configuration). Two things keep it
from being proof: the old runs were on arms zo/zof (10 s release, no fast
tables), not on fast2's settings, and the mechanism was exercised only a few times per run (0–3 chunks; run d1zc
had found 45 written chunks in 90 s on its arm, a difference I have not explained). The memory side is plain:
about 650 MiB less pinned and 400–500 MiB more available than fast2, on the scripted load; his own load is about
0.2 GiB heavier (section 36). Not seen: the picture on this arm, and his play.

**What is left of the 3.5 GiB.** The list covers two heaps and 1.0 GiB; section 39 counts 3,571 MiB of all-zero
pages. The next step in this direction is to skip without a list (whatever is a hole when a view first covers it),
which needs the canary's slices shared between runs and a count of wholly-zero 2 MiB chunks first.

### 41. His save on fast5, two minutes of play after the load, twice (2026-11-12 00:26–00:35)

The maintainer: "podmien i sam uruchom moj save (pozniej przywroc) - od chwili uruchomienia save - policz 2 minuty i
wyłącz emulator - zbierz wyniki".
- The desktop shortcut is now "BC5 emulator (0412 fast5)" (`shortcut0412b.sh fast5`); the fast4 one is in
  `~/bc5-work/trash-20261111/pulpit`.
- Runs w1his and w2his: `run0412n.sh <tag> fast5 120` (build g412u, RT on, measuring watchdog 220 MiB, no catcher):
  the scripted route (start screen, slot, Continue) on a private copy of his saves, the walk for 120 s after the
  load, then the stop. Both runs reset their private copy from the named snapshot (`1151e79071c72b17`, the copy's own
  sum); the runs never write the live saves, so there is nothing to put back. (Corrected 2026-11-12, lesson R45:
  before w2his I made the snapshot again from the live saves and compared live sums before and after; neither is
  part of the process: one named snapshot per series, hashed as the copy it is. The second copy,
  `night/saves-named.20261111-2020`, holds the same content.)

| [M] | w1his | w2his |
|---|---|---|
| ended | at G+120, 237 s | at G+120, 240 s |
| kernel lines / timeouts / crash lines | 0 / 0 / 0 | 0 / 0 / 0 |
| flips/s over the run; longest gap | 25.2; 616 ms | 25.0; 730 ms |
| pinned direct in play (150–210 s) | 11,006–11,010 MiB | 11,034–11,042 MiB |
| available memory in play; lowest of the run | 850–886 MiB | 805–823 MiB; 803 MiB |
| PSI full in play | 0.1–2.2 % | 0.0–1.3 % |
| still skipped at the end | 702 of 1,010 MiB | 686 of 1,010 MiB |

His three plays on fast2 reached 220–275 MiB available within two minutes (section 29); fast2 on this script
reaches 283–384 MiB. What these two runs are not: his hands on the pad (his load pinned about 0.2 GiB more than the
script's, section 36), and nobody looked at the picture.

### 42. His play on fast5 (2026-11-12 00:47–00:50)

The maintainer played from "BC5 emulator (0412 fast5)" (g412u `1f39cd1e`, RT on, no catchers) and wrote "zagrałem -
zbierz dane". Journal `~/bc5-data/captures/play-20261112-0047/gc/direct.log`; 185 s, he ended it himself (exit 0) [M]:
- **No ring timeout, no kernel line, no fault.** The poll before submission took 34 chunks back at 28 submissions
  (scripted runs: 0–3): his play exercises the mechanism ten times more, and nothing hung.
- Memory in play (100–181 s): pinned direct 11,462–11,720 MiB, of it **orphans 390–550 MiB**; available 462–548 MiB
  (his plays on fast2: 220–275); swap used 639 → 854 MiB; **PSI full 18–39 %**. Still skipped at the end: 444 of
  1,010 MiB (66 chunks back by CPU writes, 115 by hints, 6 runs by canary hits).
- Frames: 3,212; **252 over 100 ms, 62 s of the 183 in them**; 24 over 500 ms; the longest 2,671 ms at 169.7 s.
- **The fuse was the wall, not the box** [M for the numbers, I for the cause]: `fuse.log` gives the container
  cgroup's peak as 12,400 MiB, exactly its `memory.max`, while 460–550 MiB were still available outside it. At the
  limit every allocation of the emulator reclaims inside the cgroup first (its file cache, then swap), which is what
  a PSI of 18–39 % with free memory beside it looks like. One scripted run with the limit at 13,800 MiB (x1fuse) used
  12,518–12,665 MiB of cgroup against 12,399 at the limit (w2his); pressure and gaps were alike there (41 s against
  45–66 s with a gap over 100 ms), because the script stays 0.6 GiB lower than his play. The limit was set at 12,400
  on the night of 11-10 for unattended runs; for his play it leaves about 0.3 GiB unused.
- Orphans: with the release at 30 s idle (his "Tak, 30 s", section 28, measured on the script where it made no
  difference) his play keeps 0.4–0.55 GiB pinned under no view. At 4–10 s that was 180–340 MiB (section 29).

Not playable yet: a third of the time in long frames. Two levers measured here, neither built into his shortcut
(both change what it does and need his word): the fuse's limit, and the release's idle time.

### 43. The lean version beside (build g412L, 2026-11-12 00:55–01:05)

The maintainer: "możesz mi zbudować wersję obok - lean - ale zrób uczciwe czyszczenie wszystkiego co jest zbędne,
łącznie z przełącznikami i martwym kodem oraz wyłącz jeszcze sledzenia zmian poza emulatorem - w OS".

**What was built** (`memfast/mk0412L.sh`, `memfast/mkzpolll0412.py`, `memfast/linkmf0412l.py`, `mklean0412.py`,
`play-lean-0412.sh`; desktop "BC5 emulator (0412 lean5)" beside fast5; `bin/kyty_emulator` untouched):
- **Binary `bin-lean/kyty_emulator` `520183de`**: the main unit is g412d's plus only the zero skip's poll; none of
  the ten catchers and counters of g412j–g412t is compiled in (the build script refuses a binary that still has one
  of their switch names). The main unit and the three private units are compiled with `BC5_LEAN` (exp 0177): the
  journal, traces, tallies and frame profile are not in the code (`frame profile: t`, `guard: t`: 0 occurrences).
- **Launcher `play-pkg-0412-lean.sh`**: the title's launcher with its own `BC5_LEAN` branch opened: no `direct.log`,
  no timing or frame-profile switches, no FPS counter, audio trace, measure lines, input recorder, timeout probe; the
  emulator's output goes to /dev/null.
- **Words**: fast5's 80 less six that only write or count (`BC5_GUARD_LEDGER`, `BC5_DIRECT_TABLE_CATCHER`,
  `KYTY_BC5_EVENT_PENDING_LOG`, `BC5_DIRECT_RESET_LABEL_JOURNAL`, `BC5_DIRECT_JOURNAL_QUIET`,
  `BC5_DIRECT_ACB_INHERIT=journal`), plus `BC5_LEAN=1 BC5_LOGGING=0 KYTY_BC5_MANGOHUD=0`.
- **Beside the emulator nothing runs**: no sampler, no catcher's sampler. The fuse stays (a limit set once on the
  cgroup; it measures nothing).

**Test** [M]: started over ssh, 80 s, sampled from outside: alive with 96 threads, RSS 6.7 GiB and 1.5 GiB available
at 60–80 s (the start screen's level), no new capture directory, no sampler file, no kernel line; ended by SIGTERM.
(The first attempt failed with "wayland not available": since the reboot of 22:32 the session's socket is
`wayland-1`; a start from the desktop has the right one.) **Not tested: a load, play, the picture**: the scripted
route gates on the journal, which the lean version does not write.

**What is not lean, said plainly:**
- e8's other 47 private objects and all shared objects are the normal builds; their traces are off at run time
  (`BC5_LOGGING=0`), not compiled out. A fully lean link needs those units rebuilt from their sources.
- "Switches and dead code": the unit still carries the switches of every earlier experiment (about 70 are set by
  the launcher to turn fixes on). Removing them means making each fix unconditional and deleting the old path, in the
  15,000-line unit and in patch 0001: a change of shared code, unit by unit with its test, not a build flag.
  Section 44's audit lists what can go first.
- OS side: what runs outside the emulator and watches something is `bc5-gpu-stall-sampler.service` (root, 46 MiB,
  always on), `auditd` (root), and the user timer `bc5-compress-captures.timer` (daily). The two root services need
  the maintainer's `sudo`; this session has none and changed nothing system-wide. `bc5-gpu-watch.service` is not
  tracking: it is what reboots the box after a failed GPU reset (22:32), and stays.

### 44. Where the host copies, re-reads and double-maps the title's data (audit, 2026-11-12)

The maintainer, 00:58: "kiedy bedzie mozna pozbyc sie wyuczonych okien, czy musimy kopiowac wszystko dwa razy dla
obszarow high i low bit? tworzymy zbedne czytania; gdzie jeszcze nadmiarowo kopiujemy i odczytujemy dane gry - trzeba
rozwiazac problem a nie robić obejscia".
A subagent read g412u's unit, `memory.cpp`, the launcher and the active switches; its report, with line numbers and
each statement marked read-from-code or inferred, is in the shared notes as `exp0412-redundant-copies-audit.md`.
**I have not checked its line references myself**; the backend's sources (`backend/src`) were not in its reach, so
the filter's own copies, the shadow labels and the DMA snapshot's size are not covered. Its findings:
- **High-bit / low-bit areas ("aliases")**: nothing is copied. The same imported pages are mapped a second time at
  (byte << 40) + address; 192 MiB in 5 windows in his play [M, the journal]. The unit's own later comments say the
  stray byte was, in the cases found, another process's register left on the shared GFX ring, not a PS5 rule.
- **Learned windows**: 81 on file, each 96 MiB around a past fault; each forces the pin of every chunk under a view
  in it, and all are re-applied on every layout change. They exist because what the GPU gets mapped is found out by
  watching CPU writes and corrected by faults. They become unnecessary when every guest-mapped range is GPU-mapped
  from the start: for reads the zero buffer already does that; for GPU **writes** it does not (the zero buffer is one
  shared 2 MiB object and loses them). The change the code points to: sparse (PRT) mapping over the whole guest range
  (today only the AMM window) with real backing put in at map time.
- **Per submission**: each command buffer is copied whole two to three times and walked about ten times (chain copy,
  the filter's copy, a throwaway probe pass for light buffers, the timeout probe's copy, the soft CP's walk after
  the fence); a full state prefix goes in front of every drawing buffer (the one item with a stated price: 43.9
  against 45.0 fps); mapping upkeep (fstat per file per submission, a SEEK_DATA pass at least every 250 ms, hint
  windows of 64 MiB per new target, learned and alias re-application); label polling.
- **Behind them, seven defects** (its names): D1 GPU mappings discovered from CPU writes and faults (learned and
  hint windows, eager list, zero skip, forced syncs, forget, lazy release); D2 guest memory still treated as possibly
  anonymous (`/proc/self/maps` parse, probe pass); D3 the title shares the GFX ring's register state with other
  processes (prefixes, state restore, part of the aliases); D4 all guest queues on one kernel ring (CPU waits,
  splits, pending labels); D5 no guest interrupt from the GPU (soft-CP replay of every buffer, ring poll, flip
  drain); D6 uploads read their source late (DMA snapshot); D7 a GPU fault costs a reset (every operand checked, the
  buffer rewritten).
- **What a lean build can drop at once** (diagnostics): the timeout probe's per-job copy, the table catcher, ACB
  inherit in journal mode, timing and frame-profile lines, the ledger. The lean version of section 43 drops these.

### 45. After the review of 2026-11-12 (lessons R12, R13, R45): the poll's sample, and three corrections

- **R12, a defect in section 40's glue** (`memfast/mkzpoll0412.py` as built into g412u and g412L): after the scan
  and the sync it read the file's block count a second time and stored that. A CPU write into another still-skipped
  chunk that lands between the scan and that second read is then credited without having been scanned, and the next
  submission, even one made after that write was complete, skips its scan at an unchanged count (the reviewer's
  model: 100 -> 108 for A -> 116 for B). **Fixed:** the stored value is the sample taken before the scan
  (`memfast/zpoll0412.inc`, `zp412::look`); the host's own pin after a scan then costs one more scan at the next
  submission. CPU test `memfast/zpoll0412.cpp` on stand-ins: the targeted case (B written after the sync must be
  recovered before its next submission) passes with the new rule and fails with the old one; 20,000 random
  interleavings pass, and the old rule fails in 14,015 of them. 20,005 of 20,005.
  **Section 40's "same guarantee" is narrowed:** the block count is a hint that something was written somewhere in
  the file, not a per-chunk record; the guarantee rests on the scan running whenever the count differs from the last
  sample taken before a scan. The nine runs of section 40, the two of section 41 and his play of section 42 ran the
  defective glue.
- **R13**: section 33's intervals are between two scans; the hypothesis "the GPU read zeros" stays a hypothesis
  (corrected in place).
- **R45**: `run0412n.sh` no longer compares the named snapshot with the live saves; section 41 corrected in place.
- Section 40's "3 in 100" replaced by the counts and the test.
- **Builds with the fix** (2026-11-12 01:12-01:17): g412v `bc4356a5` in place (`memfast/mk0412v.sh`; g412u `1f39cd1e` kept) and
  the lean g412L2 `8ef2168f` in `bin-lean` (`memfast/mk0412L2.sh`); both ran `zpoll0412.cpp` on the box, 20,005 of 20,005.
  One scripted run of fast5 on g412v (y1v): 179 s, no kernel line, no timeout, 26.0 flips/s, pinned 10,982 MiB and
  823 MiB available at 150 s, 3 chunks taken back at submissions. The lean binary was not started again after the
  rebuild (its dry check passes). Both desktop shortcuts run the fixed builds.

### 46. The two parameters: the 10 s release hangs the GPU with the zero skip; the fuse goes to 13,000 MiB (2026-11-12 01:22–01:40)

The maintainer: "tak, zmien oba parametry" (the fuse to 13,000 MiB, the orphan release to 10 s, in both shortcuts).

| run (g412v, scripted load, RT on, fuse 13,000) | release | result [M] |
|---|---|---|
| z1f6, arm fast6 | 10 s | **GPU hang: gfx ring timeout at 138 s, the ring reset succeeded, the box stayed up**; the frame lasted 14.7 s |
| z2f7, arm fast7 | 30 s | clean, 179 s, 25.9 flips/s; pinned 11,004 MiB, available 848–878 MiB, cgroup 12,290–12,390 MiB |

- z1f6's hung compute buffer (#110401, 10,062 dwords, dumped beside the journal): 658 dispatches, 390 of them
  indirect, 1 wait kept for the GPU, **the largest grid 18,201,402,566,665,830,400 groups**: an indirect dispatch whose
  arguments were not the title's (and not zeros either). In the 20 s before it the release cut 220 MiB out of 18 BOs
  with 163 mappings to move, 206 chunks released, and released chunks came under a view again several times.
- **What it changes in section 40.** The four hangs with the zero skip (3 of 9 on arms zo/zof, this one) all had the
  release at 10 s; the 13 runs and his play with the release at 30 s had none, before and after the poll's fix. So
  the release's cut-and-move of mappings while jobs are in flight is at least as good a suspect for those hangs as
  the blind window [I]; the poll before submission is not shown to be what removed them. The reviewer's point about
  the two configurations was the right one.
- **Decision taken here:** the release stays at 30 s (fast6 is defined and not for play); only the fuse changes.
  **Arm fast7** = fast5's words with the fuse at 13,000 MiB. The desktop has "BC5 emulator (0412 fast7)" and
  "BC5 emulator (0412 lean7)" (the lean wrapper takes fast7's words and sets the same fuse); fast5/lean5 and
  fast6/lean6 are in `~/bc5-work/trash-20261111/pulpit`.
- Open, and a defect of ours to find: why moving mappings at a release can hand a running job wrong indirect
  arguments. The orphans it would free (0.4–0.55 GiB in his play) stay pinned until then.
- The maintainer's `sudo systemctl stop bc5-gpu-stall-sampler.service auditd.service` was refused as a whole
  because `auditd.service` refuses a manual stop; the sampler alone stops with the same command without `auditd`.
  At 01:22 the sampler was still active.

### 47. His lean7 play hung the GPU; the zero skip hangs without the "journal" words (2026-11-12 07:50–16:37)

- **His play [M].** 07:50:20 he started the desktop's lean7 (g412L2 8ef2168f, release 30 s, zero skip with its poll,
  fuse 13,000 MiB). 07:52:07 `ring gfx_0.0.0 timeout`, thread bc5-chainwd, 107 s after the start; the ring reset
  succeeded, the box stayed up; cgroup peak 12,788 MiB, no OOM kill. Lean writes no journal, so the buffer is not
  recorded; devcoredump `~/bc5-data/captures/devcoredump/20261112-075210-devcd2.txt` (not read yet).
- **The same day, another build [M, exp 0413's report].** Its integration binary e82e6547 (main unit = the lean unit
  8f6e92b3) hung at G+55 s with the zero skip and the poll on, release 30 s, BC5_DIRECT_JOURNAL_QUIET=1, none of
  lean's other dropped words; twice clean to G+240 s with the same words minus the zero skip.
- **Series on g412v [M]** (scripted route, named snapshot, RT on, 120 s after G, fuse 13,000, watchdog 220 MiB;
  `ab0412w.sh`, `raw/ab0412w.out`). Arm **lw7** = fast7's words minus the six words lean drops (BC5_GUARD_LEDGER,
  BC5_DIRECT_TABLE_CATCHER, KYTY_BC5_EVENT_PENDING_LOG, BC5_DIRECT_RESET_LABEL_JOURNAL, BC5_DIRECT_JOURNAL_QUIET,
  BC5_DIRECT_ACB_INHERIT=journal); its words equal play-lean-0412.sh's less BC5_LEAN, BC5_LOGGING, KYTY_BC5_MANGOHUD.

| run | words | result |
|---|---|---|
| a1lw 15:15 | lw7 | **GPU hang at G+61 s** |
| b1f7 15:46 | fast7 | clean, 25.3 flips/s |
| b2lw 15:55 | lw7 | clean, 25.4 |
| b4tc 16:03 | lw7 + BC5_DIRECT_TABLE_CATCHER=1 | clean, 25.7 |
| b5jr 16:08 | lw7 + LEDGER, EVENT_PENDING_LOG, RESET_LABEL_JOURNAL, JOURNAL_QUIET | clean, 26.0 |
| b6f7 16:18 | fast7 | clean, 24.9 |
| b7lw 16:23 | lw7 | clean, 24.8 |
| b8ai 16:28 | lw7 + BC5_DIRECT_ACB_INHERIT=journal | **GPU hang at G+106 s** |
| b9tc 16:34 | lw7 + BC5_DIRECT_TABLE_CATCHER=1 | **GPU hang at 100 s, before G (during the load)** |

  Every hang: ring reset succeeded, box up. b3ai did not run (exp 0413 took the lock in the same second; the runner
  refused). The NAS archive's idle-priority rsync ran from 16:02 (3 processes at the starts of b4tc..b9tc).
- **Count [M].** With all of fast7's words: 0 hangs in 16 scripted runs (14 before, b1f7, b6f7) and his one play.
  Without BC5_GUARD_LEDGER (lean7's play, exp 0413's run, a1lw, b2lw, b4tc, b7lw, b8ai, b9tc): **5 hangs in 8**.
  0 of 16 against 5 of 8: Fisher's exact p = 0.0013 two-sided, so the difference is not chance at the usual level.
  The words lean drops are therefore NOT journal-only as a set; section 43 assumed it without a test, and that
  was wrong. The lean compile is cleared: g412v hangs too.
- **Which word: not shown.** ACB_INHERIT=journal alone does not protect (b8ai), TABLE_CATCHER alone does not
  (b9tc). BC5_GUARD_LEDGER is the one word present in all 17 clean fast7 runs and b5jr and absent in all five
  hangs [M]; that it is the protecting one is an inference from one clean run of its group of four (b5jr) [I].
- **The hung buffers [M]** (a1lw acb #144379, b8ai acb #181713; dumped beside the journals in
  `~/bc5-data/captures/play-20261112-1515/gc/` and the run's own directory): compute buffers with 731 and 1,178
  indirect dispatches, the largest grid 18,413,305,064,660,664,320 and 18,443,821,864,561,147,904 groups; many
  dispatches read group counts such as 1068779520 x 1086467584 x 1067442176 from their argument addresses
  (0x12aae9ed20, 0x1213a77e20, ...): these are bit patterns of small floats (0x3fb4..., 0x40c2...), i.e. other data
  where the title's arguments should be. Same signature as z1f6 (section 46).
- **Hypothesis, not tested [I].** All skipped chunks are mapped to one canary BO, so what the GPU writes into one
  skipped chunk is readable through every other skipped chunk until the watcher takes the run back; an indirect
  dispatch whose arguments lie in a skipped chunk then reads another chunk's floats. Whether the argument
  addresses above lie in skipped chunks at the time of the hang is the next check (the journal has no view table;
  needs the views of a run or /proc/<pid>/maps). If so, the zero skip as built is unsound for memory the GPU
  writes, whatever the words, and the ledger only narrows the window.
- **Consequences.** lean7 must not be played: it is the hanging word set. fast7 stays the tested line. Section 46's
  "30 s release: no hang" holds only for fast7's full word set. For exp 0413's shared patch the zero skip stays
  launcher-only and off in code. Arm lw7 was added to play-guard-0412.sh (1137c59b; fast7's words unchanged,
  checked by the sum of the word list before and after); the copy before is play-guard-0412.sh.before-lw7-63fd0133.
- Process note: the first arm (a1lw) was started inside a slot the top session had given exp 0413, because I
  checked only the lock; the top session's slot is asked for before every series (corrected the same hour).

### 48. The zero skip's defect, a search before submission, and why the skip has to go (2026-11-12 evening)

Question (the maintainer: "find the cause and fix it"): why does the zero skip hang the GPU (section 47), and can it be
made sound?

**The defect, from the code [M]** (main unit, exp 0379's zero skip as carried by g412v). A skipped run is mapped onto ONE
2 MiB slice of the canary BO at every chunk of the run, so what the GPU writes into one skipped chunk is read back
through every other chunk of that run. The watcher looks at one slice per 50 ms, i.e. at a given slice every 1.65 s with
33 runs. On a hit the run is erased and the title's own (zero) pages replace the canary: what the GPU wrote is lost.
Every run of section 47 has such hits, fast7's too (recount with the exact line "canary hit in run": a1lw 4, b1f7 7,
b2lw 5, b4tc 5, b5jr 5, b6f7 4, b7lw 7, b8ai 7, b9tc 4; always runs 21, 5, 6, 8 first). That the hung buffers' arguments
(float bit patterns read as dispatch group counts) came from memory under the canary is [I]; no address was checked.

**Correction of section 47 [M]:** its text says "4-10 canary hits per run"; that count came from a pattern that also
matched statistics lines. The numbers above are the real ones. Section 47's causal limits stand (Codex): the hang counts
compare different binaries, word sets and exposure, the NAS rsync ran through most arms, and which word protects is not
shown.

**The candidate fix: BC5_GUARD_ZSKIP_SCAN=1|2** (tag zs412; `memfast/zscan0412.inc`, glue in `memfast/mkzscan0412.py`,
CPU test `memfast/zscan0412.cpp`: 14,642 of 14,642; `nscan0412.cpp` 13,435 of 13,435). Default off. Before every
submission the command buffer and the tables it points to (2 KiB each, read through the direct memfd) are searched by
value for addresses under the canary, and that memory gets its real pages before the buffer goes out: mode 1 the whole
run, mode 2 an 8 MiB window from the find. Review R25 (Codex) applied before any run: `ns412::scan` reports whether a
capacity limit (4,096 finds, 1,024 table candidates) cut it short, and after an incomplete search, or a table that
cannot be read in full, every run under the canary comes back.

**Build g412w** (`memfast/mk0412w.sh`, kit `memfast/kit-w.sha256`): g412v's chain plus the scan, binary BESIDE the one in
place: `~/bc5-work/exp0412/bin-w/kyty_emulator` 1d22954ffc9a1d7219889f7f34223f43; `bin/kyty_emulator` (g412v, bc4356a5,
fast7's) untouched and re-checked. Limit: the shared build's objects were rebuilt by exp 0413 at 17:54 (patch 0001
01abfc0c), and g412w links those for every unit that is not private, so g412w is not exactly "g412v + scan"; the three
control arms below run the same binary without the scan for that reason. `run0412n.sh` takes `N_EMU` for the binary
beside (the launcher's `BC5_EMU`).

**Series** (`ab0412x.sh`, raw `raw/ab0412x.out`, `raw/ab0412x-summary.txt`, per-arm files on the box under
`~/bc5-work/exp0412/night/raw/<tag>-*`; scripted route, 120 s after G, RT on, fuse 13,000 MiB, watchdog 220 MiB;
18:06-19:08, the NAS rsync running in every arm; word set lw7 = fast7 less lean's six words, the set that hung 3 of 7 on
g412v):

| arm | scan | result | canary hits (runs) | skip ends | lowest available |
|---|---|---|---|---|---|
| c1s1 | 1 | clean, 25.5 flips/s | 1 (21) | 46.7 s, incomplete search | 305 MiB |
| c2s2 | 2 | clean, 25.5 | 1 (21) | 46.6 s, incomplete (1,124 finds) | 334 |
| c3s0 | off | clean, 24.9 | 4 (21, 5, 6, 8) | 704 MiB still skipped at the end | 894 |
| c4s1 | 1 | clean, 25.1 | 1 (21) | 46.6 s | 445 |
| c5s2 | 2 | clean, 24.2 | 1 (21) | 46.1 s (76 finds) | 376 |
| c6s0 | off | clean, 25.5 | 4 (21, 5, 6, 8) | 704 MiB still skipped | 883 |
| c7s1 | 1 | **title crash** at 244 s, before G+120 (G at 216 s, a gap of 8.6 s) | 1 (21) | 46.8 s | 198 |
| c8s2 | 2 | clean, 25.4 | 1 (21) | 45.8 s (88 finds) | 359 |
| c9f1 | 1, fast7's words | clean, 24.8 | 0 | 46.4 s | 331 |
| d1s1 | 1 | clean, 26.0 | 1 (21) | 46.8 s | 321 |
| d2s2 | 2 | clean, 25.2 | 1 (21) | 45.5 s (55 finds) | 308 |
| d3s0 | off | **GPU hang** at G+61 s (ring gfx timeout, reset succeeded; devcoredump `~/bc5-data/captures/devcoredump/20261112-190716-devcd7.txt`) | 5 (21, 5, 6, 8, 32) | off after the hang | 437 |

Result [M]:
- Under the scan: 0 GPU hangs in 9 arms, but canary hits remain: 1 in each of the 8 lw7 arms, always run 21 at about
  34 s (0 in the one fast7 arm). The search by value does not find the address of that write. Without the scan on the
  same binary: 4, 4 and 5 hits and 1 hang in 3 arms. 0 in 9 against 1 in 3 is not a difference (Fisher p = 0.25).
- At 45.5-46.8 s, in the loading screen, every scan arm meets a buffer whose search is incomplete (over 1,024 table
  candidates; in mode 2, where more is still under the canary, 55 to 1,124 real finds in that one buffer) and all
  skipped memory comes back. From then on the run has no zero skip: pinned peaks 11.67-11.80 GiB against 10.97-11.06,
  lowest available 305-445 MiB against 883-894.
- Cost of the scan to that point: 3.3-3.4 s of the submitting thread in 41 s, about 790,000 table reads.
- c7s1's crash is the title's own access violation (a read of address 0 in guest code at 0x903a05f35, registers holding
  text), after a load twice as slow as the other arms' and the lowest memory of the series (198 MiB). Whether the scan,
  the memory level or the rsync is behind it is not shown [I: memory pressure]. `raw` on the box: `c7s1-crash.txt`.

**Reading.** The accepted criterion was "0 canary hits and no hang under the scan". It is not met: hits remain. The
series also shows why the skip cannot be repaired by searching: the title hands the GPU hundreds of addresses inside
memory that read zero when the list was made. "Zero at list time" does not mean "the GPU will not write here", addresses
a shader computes cannot be found by value, and a canary can only report a write after the data is already in the wrong
place. So the zero skip is unsound by design and BC5_GUARD_ZSKIP_SCAN does not make it sound; with the scan the skip
also saves nothing after 47 s.

**Proposal (the maintainer's decision, his shortcut):** take BC5_DIRECT_ZERO_SKIP out of fast7 too. It stays out of
the shared default either way. The price, measured above: about 0.55 GiB less available memory on the 120 s route
(about 300-450 MiB lowest instead of about 890), i.e. the memory wall comes back for long play and has to be removed by
other means (sections 9-22's levers; the reason memory under the skip is pinned at all is that the title names it to the
GPU). BC5_GUARD_ZSKIP_SCAN stays in g412w as a default-off diagnostic; it is not proposed for any shortcut.

**Decision (the maintainer, 2026-11-12 19:25: "yes, remove it"):** arm `fast8` in `play-guard-0412.sh` = fast7 without
BC5_DIRECT_ZERO_SKIP and BC5_GUARD_ZSKIP_POLL_SUBMIT (dry runs on the box: fast7's output identical before and after,
fast8 differs by those two words, 78 words instead of 80). Launcher on the box a547d77c, the previous kept as
`play-guard-0412.sh.before-fast8-1137c59b`; binary unchanged (g412v bc4356a5). Desktop: "BC5 emulator (0412 fast8)";
fast7's shortcut moved to `~/bc5-work/trash-20261111/pulpit`. fast8 has not been run.

Not done: no run of fast7's words without the zero skip on this route today (the memory figure above is from scan arms
after their skip ended); the address behind run 21's write; a check of hung arguments against the canary's ranges.

### 49. The memory architecture against other emulators (design study, 2026-11-12 night; laptop only, nothing run)

The maintainer's order through the top session: why other emulators, and a PS4 emulating a PS5, do not hit the wall,
and whether ours must be rebuilt. The study is `DESIGN-memory-architecture.md`. Sources read at named commits: shadPS4
`b97bafa3`, RPCSX `e8ae1481`, RPCS3 `9b8974d3`, the yuzu line (Eden mirror `e9661b2a`), Kyty `4733b7e1`, KytyPS5 through
exp 0414, Linux v6.19 with v7.1 diffed (amdgpu userptr, dma-buf import, TTM swap, udmabuf, PRT, faults).

- **Why they have no wall [S]:** all of them keep guest RAM as ordinary swappable shared memory, recompile the guest's
  shaders and hand the GPU copies of what a draw uses. The GPU never sees a guest address, so they always know which
  bytes it needs. Their price: copies, write-protect faults, hashes, read-backs that drain the GPU; shadPS4 by default
  does not return GPU writes at all.
- **Why we pin [S/M]:** GPU VA = guest VA with native shaders and no translation; the GPU cannot wait for a page (F53).
  The console holds the same memory resident. Ours on top of that: `udmabuf` allocates and long-term pins every page
  of a range, written or not (kernel `memfd_pin_folios`), which is where the 3.5 GiB of zero pages come from; every
  heap is imported whole, so CPU-only data cannot swap; and the non-guest side needs 3.2–3.6 GiB.
- **Kernel facts that close two ideas [S]:** amdgpu userptr BOs are not pinned but are re-faulted on every submission
  that lists them (F38's 5 ms per GiB); GPU-owned BOs are swapped by TTM only against its own limit, never on memory
  pressure.
- **Recommendation:** keep the direct architecture; (A) reproduce the console's budget outside the title (bare play
  session, host copies, driver buffers, orphans, then the 12,800 MiB offer): 0.7–1.1 GiB against a deficit of 0.4–0.5;
  (B) stop creating never-written pages, soundly, only after experiment E1 (what the GPU does at a PRT page and at a
  read-only page on gfx1013) and after the one writer the last series could not name is known: up to 2.8 GiB; (C)
  CPU-purpose heaps out of the pin after a long clean scan: 1.6 GiB swappable. The copy-and-translate model is a
  different emulator and is not proposed.
- **Split with exp 0415 (agreed):** it builds the lock side (imports prepared outside the device mutex, `wait_jobs`);
  this experiment the memory side (what is imported, when it is given back). Diffs to `direct_sync_one` are exchanged
  before a build.

### 50. Option A, first item: the scripted route with and without Plasma's shell (2026-11-12 22:10–22:33)

On the maintainer's "Tak, wariant A" and "przy czym uruchomienie gry musialoby ubić plazmę". `ab0412y.sh`: four runs
of `run0412n.sh <tag> fast8 120` (g412v `bc4356a5`, RT on, no zero skip, fuse 13,000/2,048, watchdog 220 MiB, the
private save and learned copies), order shell, bare, bare, shell; "bare" = `plasma-plasmashell.service` stopped for
the run and started after it. `snap0412.sh` took whole-box snapshots at 25, 60, 130, 165 and 225 s. Kernel
7.2.15-ogc1.1; the box up since 11-11 22:32; three rsync processes (the NAS archive) in all four; no steamwebhelper.
Data: `raw/ab0412y.out`, `raw/y{1sh,2ba,3ba,4sh}-{snap,watchdog,summary}.txt`; the kernel log was streamed to the
laptop for the whole series: no line.

| run | shell | lowest available | highest PSI full | seconds with a gap over 100 ms | longest gap | flips/s | available at 165 / 225 s | AnonPages | GPUActive | VRAM used (of 512) | the emulator's VRAM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| y1sh | running | 497 MiB | 23 % | 98 | 1,328 ms | 23.0 | 632 / 656 | 353 / 348 | 499 / 502 | 502 | 352 |
| y2ba | stopped | **724** | 12 % | 55 | 659 ms | 24.0 | 805 / 862 | 262 / 282 | 372 / 372 | 480 | 431 |
| y3ba | stopped | **775** | 15 % | 67 | 628 ms | 23.9 | 856 / 839 | 251 / 243 | 369 / 371 | 488 | 439 |
| y4sh | running | 560 | 14 % | 73 | 735 ms | 24.0 | 663 / 691 | 296 / 302 | 483 / 485 | 511 | 335 |

[M] All four reached G+120 with no kernel line and no crash line. Pinned direct memory at the end 11,660 MiB in y1sh
(the ledger), GTT 12.3–12.5 GiB in all.

**Reading.**
- [M] Without the shell the lowest available memory of the route is **+221 MiB** (750 against 529, means of two), and
  +175–190 MiB at the 165 and 225 s snapshots. Two runs an arm, the arms do not overlap (724, 775 against 497, 560).
- [M] Where it comes from: the shell's own pages (142–176 MiB resident plus 101–135 MiB already pushed to swap by the
  time of the wall, so its resident part is what counts) and its GPU memory: by fdinfo 90–126 MiB of **VRAM** and
  16–54 MiB of GTT. `GPUActive` is 111–130 MiB lower without it and `AnonPages` 50–90 MiB lower.
- [M] The 512 MiB VRAM carve-out is full with the shell (502–511 MiB used). Without it the emulator's own VRAM share
  rises from 335–352 to 431–439 MiB: about 90 MiB of the emulator's driver buffers move from system RAM into VRAM that
  the shell had held. That is part of the gain and it is free.
- [M] Still there in the bare runs: `plasma-keyboard` 74 MiB of GTT (the on-screen keyboard, a child of KWin, never
  shown during play) and Xwayland 22 MiB. The next 0.1 GiB of this option.
- [I] The long frames follow: 55–67 s with a gap against 73–98, the longest gap 0.63–0.66 s against 0.74–1.33 s.
  One series; the direction agrees with the memory.

**The mechanism he asked for** ("the game launch would have to stop Plasma") exists since section 30 and was run for
the first time: `lean0412.sh stop <pid>` stopped the unit and its watcher started it again 24 s later, when the
stand-in process had ended (`lean.log`: stopped 22:32:36, started 22:33:00; plasmashell pid 3326867 afterwards). In
the series the unit was stopped and started twice more by `ab0412y.sh`'s own trap. It is `BC5_0412_LEAN=1` in the
shortcut's environment; the shortcut was not changed then.
**2026-11-13 00:48, on his "Tak, włącz":** the desktop has "BC5 emulator (0412 fast8 bez Plasmy)" (`Exec=/usr/bin/env
BC5_0412_LEAN=1 … play-guard-0412.sh fast8`); the fast8 shortcut went to `~/bc5-work/trash-20261111/pulpit`. The
launcher's dry run with the switch names the unit it would stop; it has not been run with the game yet.

**What it is against the deficit.** 0.22 GiB of the 0.4–0.5 GiB (section 16), 0.3 GiB with the keyboard and
Xwayland. On his own load the pin is about 0.2 GiB higher than on the script's (section 36).

### 51. The learned windows: what the file holds today and what each window does (2026-11-12 22:33–22:40, reads only)

On the maintainer's "Wyuczone okna nie są rozwiązaniem tylko obejściem. Zleć znalezienie rozwiązania". The design is
`DESIGN-learned-windows.md`; this section is its first measurement. `learnclass0412.py` sums the host's own journal
lines per window over run y1sh (`~/bc5-data/captures/play-20261112-2211/gc/direct.log`, 262 s, scripted route);
output `raw/learnclass-y1sh.txt`.

[M]
- The file: **81 windows** of 96 MiB (`cb30371e`), their union 6,432 MiB of address space. By place: 34 in the
  0x11… block, 26 in 0x12…, 9 in the AMM window, 3 in 0x13…, 3 in 0x14…, one each at 0x0b…, 0x10…, 0x17…, 0x26…,
  0x54…, 0x7f…. No line with a bit above 40 any more (those went to the alias file, 5 lines).
- **No window was learned tonight**: none in y1sh, none in exp 0415's d1 and d2, and exp 0415's private copy after its
  873 s run equals the shared file. The file's last two lines are 0x1112… and 0x11fe….
- What the windows did in the run:
  - forced chunks of the direct file under views: 4,778 MiB counted (an upper bound: the journal counts every chunk
    under a view in a window, most of them inside heaps that are imported whole anyway);
  - **anonymous memory handed over as userptr: 0 MiB.** That kind does not exist today;
  - **zero buffer over addresses where the guest has no range: 2,042 MiB of address space** (no memory: one shared
    2 MiB buffer). **15 windows lie wholly in such holes** (0x0b8a…, 0x1112…, 0x1116…, 0x1206…, 0x12ba…, 0x12c6…, 0x12ca…, 0x130a…,
    0x1332…, the three at 0x14…, 0x1762…, 0x2672…, 0x5452…): they exist only so
    that an access to an unmapped address does not stop the GPU. 22 more are part hole, part heap.
  - The 9 AMM windows: 872 MiB under views, 158 MiB of holes, filled and given back 4–50 times each in the run.
    The AMM window has had a PRT background by default since F257 (`play-pkg.sh` line 111); exp 0201's run without
    these 9 had no fault.
- Cost: 990 full passes of `learned_apply` over 5 ms, 9.7 s in the 262 s run (exp 0415 tonight: 626–648 passes, 6.1–6.3
  s per 115 s; 1.9–2.5 s of device-mutex time per load phase).
- What is pinned only because a window (or a hint) forced it: at most the 148 MiB under lazy views, plus an unknown
  part of the 1,392 MiB under by-data views (the ledger of y1sh at 242 s). Under eager views (9,984 MiB) the windows
  add nothing.
- **What the rule "pin every view when the title maps it" would cost:** views 12,186 MiB, pinned under a view
  11,418 MiB: **+768 MiB** on this route (`AssetHeap Large` 316, `InitAllocator` 198, `AssetHeap Small` 120, 24 small
  heaps 134). The design's first estimate (0.26–0.49 GiB) compared against the pin including orphans and was too low.

**Reading [I].** The windows are three different things under one name: (1) holes, where the cure is a "no fault"
background and no memory at all (15 windows wholly, 22 in part); (2) heaps that are imported whole anyway (most of
the 0x11… and 0x12… windows: dead weight, they only cost the passes); (3) by-data and lazy heaps, where a window is
the only reason a never-written chunk is pinned: the one kind with a real question behind it (does the GPU write
there, or only read zeros?). Which windows are of kind (3) is what a run with an empty file shows; asked of the top
session. The full rule costs 0.77 GiB at the wall, so it cannot go in before options A–C have made room; the PRT
background (kind 1) costs nothing and can.

### 52. The scripted route with an empty learned file: no fault, nothing learned (2026-11-12 22:48–23:02)

The top session's slot and conditions (one run first, stop at the third GPU reset, the shared file never written).
`run0412n.sh` got two options, defaults unchanged: `N_LEARN=<file>` (the source of the run's private copy) and
`N_RESETS=<n>` (ride out n−1 recovered GPU hangs). Runs on today's build with no code change: arm fast8, g412v
`bc4356a5`, RT on, fuse 13,000/2,048, watchdog 220 MiB, the shell running, three rsync processes, kernel log streamed
(no line). Data `raw/z1emp-*`, `raw/z2emp-*`; the control is section 50's y1sh and y4sh, 37 and 20 minutes earlier
in the same boot.

| run | learned file | play after G | ended | GPU faults / timeouts | windows learned | flips/s | s with a gap over 100 ms | pinned direct at 230 s | highest PSI full | lowest available | `learned_apply` passes over 5 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| y1sh | 81 windows | 120 s | G+120 | 0 | 0 | 23.0 | 98 of 257 | 11,606 MiB | 23 % | 497 MiB | 990, 9.7 s |
| y4sh | 81 windows | 120 s | G+120 | 0 | 0 | 24.0 | 73 of 239 | 11,670 | 14 % | 560 | |
| **z1emp** | **empty** | 120 s | G+120 | **0** | **0** | 24.7 | 57 of 235 | **11,438** | 11 % | 407 | 535, 3.6 s |
| **z2emp** | **empty** (z1emp's, 0 lines) | **420 s** | G+420 | **0** | **0** | 25.0 | 79 of 537 | 11,506 | 11 % | 424 | 907, 6.5 s in 542 s |

[M]
- **Not one of the 81 windows is needed on this route**: 783 s in two runs (540 s of it play), the start, the menu and the
  save load twice, with no GPU fault, no timeout line in the journal, no kernel line, and the private file still
  empty at the end of both. The shared learned file and the alias file kept their checksums.
- Without the windows the pin is **228 MiB lower from the first ledger line** (8,206 against 8,434 MiB at 10 s) and
  170–230 MiB lower in play; by heap: `AssetHeap Large` 428 against 500–504, the 24 small heaps 314 against 460.
  That memory was pinned for no use the route shows.
- The ledger's PSI "full" during play is 0–12 % against 7–21 %; the passes of `learned_apply` cost a third (what is
  left is the 2 MiB guards behind the eager heaps: 11 zero-buffer lines in the run against 2,042 MiB of them).
- The lowest available memory is **not** better (407 and 424 against 497 and 560): the emulator kept more of its
  own memory resident instead (resident 3.6 GiB against 1.0–1.3 at 230 s, swap 92 against 161 MiB) [M]; why the
  lower pin does not show as available memory is not explained. Two runs against two.

**What it does not show.** His own play: the windows were learned at the pause menu, in Photo Mode, at the lake and
in fights (F53, F257, F468, F687), none of which the scripted route visits. A fault there with an empty file is a
14 s freeze, so the file cannot simply be dropped from his shortcut: the route says the windows are dead weight
here, and the rule of `DESIGN-learned-windows.md` is what has to cover the places the route does not reach.

**Answer to "what do the 15 hole windows map"** [C][M]: each maps our shared 2 MiB zero buffer, read-write, 48 times
over its 96 MiB (the guest has no range there), re-derived on every layout change. With the empty file those
addresses were unmapped for 783 s and nothing touched them. They are the record of single stray accesses
(F92, exp 0040, 0042), kept for ever.

### 53. Build g412x with the rule's three switches; the series ended in a GPU hang and a reboot in the arm with R1 and R2 (2026-11-12 23:50 – 11-13 00:12)

**The build** (`memfast/maprule0412.inc`, `mkrule0412.py`, `mk0412x.sh`, tag mr412; all three default off):
`BC5_GUARD_MAP_RULE=1|2` (R1: every chunk under a view is imported when the view exists; one condition in
`direct_sync_one`), `BC5_GUARD_PRT_BG=1` (R2: one PRT mapping from 4 GiB to 0x9000000000 at device open, acting only
with R1 on, so that a miss of a guessing import policy cannot turn silent; `scratch_fill` does nothing inside it),
`BC5_GUARD_LEARN_LOG=1|2` (the catcher: one "would learn" line per fault with what lay at its address; the learned
and alias files are not written). CPU test `maprule0412.cpp`: 15,281 of 15,281 on the laptop and on the box. Build
g412x = g412w + this, unit `15fc40ee`, binary `655a86fc` beside (`bin-x`); g412v `bc4356a5` in place and g412w
untouched. `raw/mk0412x.out`. The diff went to exp 0415 before the build; no objection.

**The series** (`ab0412r.sh`: bin-x, arm fast8's words, the scripted route, 120 s after G, RT on, fuse
13,000/2,048, watchdog 220 MiB or PSI full 60 %, the shell running, 3 rsync processes, kernel log streamed; stop at
the first kernel line). Planned c0 c4 r1 r2 r2 r1 c4 c0; **four ran**. Data `raw/ab0412r.out`, `raw/{c0a,c4a,r1a,r2a}-*`,
`raw/r2a-kernel-stream.txt`. Boot age 25.3–25.6 h.

| run | learned file | switches | ended | lowest available | highest PSI full | pinned direct | flips/s | kcompactd0 / kswapd0 CPU |
|---|---|---|---|---|---|---|---|---|
| c0a | 81 windows | none | G+120, 239 s | 411 MiB | 10 % | 11,764 MiB | 24.8 | 80 / 12 s |
| c4a | empty | LEARN_LOG=1 | G+120, 239 s | 446 | 9 % | 11,518 | 26.0 | 100 / 8 s |
| r1a | empty | MAP_RULE=1, LEARN_LOG=1 | **the watchdog killed it at 190 s** (PSI full 76 %, available 257) | 239 (ledger) | 76 % | 12,030–12,200 | 18.4 | 62 / 63 s |
| r2a | empty | MAP_RULE=1, PRT_BG=1, LEARN_LOG=1 | **GPU hang at 153 s, the box rebooted** | 219 (ledger) | 65 % | 12,188 | | |

[M]
- **c0a against c4a, the same binary, 5 minutes apart:** without the learned file the pin is 246 MiB lower, the
  lowest available memory 35 MiB higher, no fault, no "would learn" line, nothing learned. With section 52 that is
  three runs of the route without the file and no fault. **Section 52's lower "lowest available" without the file
  (407, 424 against 497, 560) did not repeat** on one binary in one quarter of an hour. One pair: it shows the
  difference is not stable, not what caused it (review R13). Section 52 compared runs 20–37 minutes apart in a session whose compaction load was climbing (kcompactd0
  80–100 s of CPU per 4-minute run here; exp 0415 measured 3–9 s per phase early in the same boot and 16–20 s later).
- **R1 goes to the wall in the menu.** With every view pinned whole the pin is 9,624 MiB at 10 s (8,206 without the
  file, 8,434 with it) and 12,114 MiB at 60 s, before the save is loaded; available memory stays at 240–280 MiB from
  50 s on, PSI full reaches 32–76 %, a 7.7 s frame. The watchdog ended r1a at 190 s. No GPU fault, no kernel line.
  The heaps are whole (`AssetHeap Large` 816 of 816, `InitAllocator` 652 of 652, `Wwise` 220 of 220). That is the
  +0.77 GiB of section 51 arriving, plus what the title maps before play and gives back later.
- **r2a:** the PRT span was accepted (`PRT window 0x100000000+0x8f00000000: 0` in the run's log). Memory as in r1a
  (12,188 MiB pinned at 133 s, available 256–278 MiB, PSI full 52–65 %; the watchdog's limits were not crossed five
  samples in a row). At 00:10:41, 153 s into the run and 3 s after G, `ring gfx_0.0.0 timeout` (thread `bc5-ring`),
  **no page fault** (the devcoredump's fault address and status are 0), `Ring gfx_0.0.0 reset failed` 0.19 s later,
  and `bc5-gpu-watch` crashed the kernel for a reboot as it is built to. The box was back at 00:11:54 with Plasma.
  On the box, never committed (the title's buffers): `~/bc5-data/captures/play-20261113-0008/gc/` (journal, two dumped
  buffers: a draw buffer of 20,324 dwords, submission 97741, and a compute buffer of 5,171 dwords, 97744),
  `~/bc5-data/captures/devcoredump/20261113-001041-devcd8.txt`, three pstore records of 00:11.
  The shared learned and alias files, g412v and the saves kept their checksums.

**Reading [I].** One hang. Against r1a, which met the same wall for 140 s without a kernel line, this run differs by the
PRT span and by chance. It cannot be said which. For the memory wall speak the fault-less ring timeouts under memory pressure already on record (F260:
three machine-downs at 346–490 MB available, two of them without any PRT). For the PRT span speaks only that it was
the one difference to r1a, which ended without a kernel line. A PRT page cannot produce a fault, and a job that reads
zeros where it faulted before could loop instead (section 38's pattern); but with the empty file nothing in 1,022 s
of this route touched an unmapped address at all (sections 52 and here), so there was nothing for the span to change
unless the wall changed the route. Not settled.

**What is settled.**
- R1 "pin every view whole" is not runnable on this box today: it reaches the wall before the save loads. It needs
  options A–C first, or a form that does not create never-written pages (option B, behind experiment E1).
- Today's import policy without the learned file (arm c4) is the cheapest arm measured: 246 MiB less pinned, no
  fault on this route in three runs. What it risks is a 14 s freeze at each place of his play the route does not
  visit, once per run (LEARN_LOG=1 keeps the window for that run).
- R2 has to be tested apart from the wall: with R1 off it would hide misses (the top session's point 3), so its own
  clean test is R2 over holes only, on a run that is not at the wall. Not built: the switch refuses to act without R1.

### 54. Reads after the reboot: what hung in r2a (2026-11-13 00:12–00:20, reads only, the top session's GO)

**Intact by checksum** [M]: g412v in place `bc4356a5`, g412w `1d22954f`, g412x `655a86fc`; the shared builds
`ce0e3b92` and `35ec3341`; `play-pkg.sh` `157021e3`; the shared learned file `cb30371e` and alias file `1bbc544b`;
`play-guard-0412.sh` `a547d77c` and the fast8 shortcut's Exec line; the named save snapshot of the runs
(`1151e790`, the runner's own sum); no file of the memory-heavy snapshot or of `~/bc5-work/_SaveData/PPSA03671` is
newer than the evening.

**The arm** [M]: r2a, build g412x, arm fast8's words plus `BC5_GUARD_MAP_RULE=1 BC5_GUARD_PRT_BG=1
BC5_GUARD_LEARN_LOG=1`, an empty private learned file. **Both MAP_RULE and PRT_BG were on.** The PRT span was mapped
(`PRT window 0x100000000+0x8f00000000: 0`).
- How far: the journal's t 147.1 s, the run's 153rd second; the save was still loading (the route's G was set "by
  time" at 150 s because the title had not reached 20 flips/s), so 0 s of play.
- The submissions: #97739 and #97740 ended in 0.5–0.6 ms at t 147.08–147.10 s. Then **#97741, a draw buffer of 20,324
  dwords** (40 dispatches, 291 label writes) and **#97744, a compute buffer of 5,171 dwords**, both on the GFX ring,
  both timed out at 2.0 s with fault address 0 and status 0. The journal's operand filter passed both with
  `unmapped 0` against 20,924 mappings; the table catcher found none of 256 hashed slots changed.
- The devcoredump (`20261113-001041-devcd8.txt`): ring gfx_0.0.0; `CP_IB1_BASE` 0x100d00000000 (the device's own
  buffer slot at 16 TiB), `CP_IB1_CMD_BUFSZ` 0x5608 with `CP_IB1_BUFSZ` 0x1708 left: the command processor stood
  **inside the draw buffer, 16,128 of 22,024 dwords in**; `GRBM_STATUS` 0xa2712028 (the recovered hang of 19:07,
  devcd7: 0xa0407028, 0x3b8 dwords left of its buffer); no page fault in either. The bits are not decoded here
  (TODO(verify) against the gfx10 register header).
- Memory at that moment (ledger, t 133 and 144 s): pinned direct 12,188 then 11,410 MiB, available 278 and 256 MiB,
  PSI full 65 and 52 %, GTT 12,741 then 12,170 MiB, 97,744 → 155,678 major faults.
- Mapping changes just before: between t 133 and 144 s the orphan release cut 214 and then 868 MiB out of 32 BOs and
  moved 361 mappings (the title gave back what it had mapped for the load; with R1 on, orphans had reached 1,615 MiB
  against 220–310 in the other arms). The mapping count was steady at 20,924 for the last submissions.

**What kind of hang** [I]. Not decided. The command processor stood inside the buffer the journal calls a draw
buffer, but that buffer holds 40 dispatches, so its name and the position neither assign the hang to a draw nor
exclude a compute or ray-tracing job that never ends (F403); the compute buffer timed out with it, as the pair did
in F260 and in section 38. The filter's `unmapped 0`, the steady mapping count and the ledger's samples were taken
at submission and afterwards: they do not show which mappings existed, or changed, while the job ran (review R13). What R1/R2 **could** have done and is not excluded:
(a) with the PRT span, the 361 mappings moved by the orphan release were for a moment PRT pages instead of unmapped
ones, and so was everything the release cut: a job that reads there now gets zeros without any sign, where before it
would have faulted loudly (in no earlier run did it fault, so nothing is known to read there); (b) R1 made the
release five times larger than in any earlier run, 3–14 s before the hang. Against both stands the plain memory
state: PSI full 43–65 % for 25 s, the worst of any run of this experiment that reached the load.
**Why the reset failed** is not known: the same kernel recovered the ring at 19:07 and failed here, at F260 and in
section 38; in all three failures a draw buffer and a compute buffer had timed out together. That is a correlation
from four dumps, not a cause. One run with R1, R2 and heavy memory pressure at once isolates neither the hang nor
the failed reset; that the kernel accepted the PRT span says nothing about what the span costs, and its size alone
explains no reset failure.

**So:** MAP_RULE and PRT_BG stay off and are not to be run together again until R2 has a test of its own away from
the wall, and the orphan release under R1 is looked at (it should not have 1.6 GiB to cut).

### 55. E1: what gfx1013 does at a page without backing (2026-11-13 04:50–04:57)

On the maintainer's "zgoda" to the question that named raw GPU submission and a possible reboot; the top session's
slot after the integration. Plan `E1-plan.md`; tool `e1/e1-probe.cpp` (binary `e0351ced` at the cases that count),
runner `e1/e1run.sh`; one process and one lock line per case, the kernel log streamed. Kernel 7.2.15-ogc1.1, DRM
3.64, uptime 4.7 h, no emulator, Plasma's shell running. Data `e1/raw/case-N.out`, `case-N.dmesg`,
`e1/raw/e1-kernel-stream.txt`. Programs: the backend's gfx10 buffer-clear and IGT's gfx10 buffer-copy
(`lib/amdgpu/amd_shaders.c:321-324` @ 9d4b6ef, MIT), 16 KiB a job, GFX ring.

| case | job | result [M] | kernel lines |
|---|---|---|---|
| 0 control | clear `real`; copy `real` to `out` | both as written; fences 0.05 and 0.03 ms | none |
| 1 PRT read | copy from a PRT page to `out` | **`out` all zero**; 0.05 ms; fault register empty | none |
| 2 read-only read | copy from a page mapped readable only to `out` | `out` all zero | none |
| 3 PRT write | clear a PRT page | completed in 0.05 ms; fault register empty; the follow-up clear and copy ran | **none: the write vanishes without a sign** |
| 4 read-only write | clear a page mapped readable only | **the job never completes**: fence timeout at 2.03 s; `AMDGPU_INFO_GPUVM_FAULT` = address 0x100a02000, status 0x00741041; the read-only BO still all zero; context reset state 3; a new context ran clear and copy correctly **15 s after the timeout** (the tool waits 15 s before it looks: when a new context became usable was not measured) | `[gfxhub] page fault` at 0x100a00000–0x100a03000 (client TCP, `PERMISSION_FAULTS: 0x4`, `RW: 0x1`), 2.03 s later `ring gfx_0.0.0 timeout`, `Ring gfx_0.0.0 reset succeeded` 0.1 ms after it, `device wedged, but no recovery needed` |

No `reset failed`, no GPU reset, no reboot; `bc5-gpu-watch` armed and disarmed. A devcoredump of case 4 was saved
(`~/bc5-data/captures/devcoredump/20261113-045658-devcd1.txt`; our own test job, still not committed).

**A fault of the tool found by the control, and fixed before the cases that count.** The first two control runs
(kept as `case-0-first.out`, `case-0-second.out`, and `case-5-first.out`) used one command buffer for all jobs,
rewritten between them: the "copy" left its destination untouched, also 200 ms later, and in `case-5-first` a
buffer the CPU had refilled came back holding the earlier clear's value: **the GPU ran the previous job's dwords
again**. With a command buffer of its own for every job the control is right. Why a rewritten buffer was not seen
is not known (TODO(verify); the direct path rotates its buffer slots, so it is not known to be exposed).

**What it decides** (design section 7 and `DESIGN-learned-windows.md`):
- **Reads are safe on both kinds** [M]: a shader's read of a PRT page and of a read-only page gives zeros with no
  fault and no cost. A never-written page can be shown to the GPU with no memory behind it, as far as reads go.
- **A PRT page swallows writes silently** [M]. R2 therefore must never lie under memory the title mapped and we
  chose not to import: a GPU write there is lost and nothing says so (the zero skip's defect, section 48, in
  another form). Under addresses the title did not map it is the console's behaviour (F257).
- **A read-only page is a write detector, in this one sample without a game** [M]: a GPU write to it is a named
  fault (the address and status are readable from user space), the page is intact, the job is lost and the ring
  is reset. Measured: the fence timeout at 2.03 s and the kernel's reset line 0.1 ms after its timeout line;
  a new context usable at +15 s (the tool slept 15 s first, so nothing earlier is known). It detects the write;
  it does not restore it. The reset is the one that has failed three times under the title's load (F260,
  sections 38 and 53).
- For option B this is a **detector, not yet a floor** [I] (review of 2026-11-13). Never-written chunks under a view
  could be mapped **read-only onto one zero BO** instead of being created and pinned: reads are right (the file
  holds zeros there) and nothing can be written into the shared zero page, so nothing is aliased. A GPU write
  then faults with its address. What that does NOT give: (1) the write itself: the job is lost, and running the
  whole job again can double what had already taken effect before the fault (atomics, appends, labels), so a
  replay is not known to be sound; (2) the CPU's side: the GPU's read-only mapping does not see the CPU's first
  write into such a chunk, so the mapping has to be switched to the real page on the CPU's first write as well,
  consistently with the GPU; (3) a price: the stall per first GPU write is at least the kernel's 2 s and today
  14 s (the recovery code sleeps 12 s); how many chunks the GPU writes first decides whether that is bearable.
  Section 51's 768 MiB of never-written chunks under views is the upper bound of the saving on the route,
  section 39's 3,571 MiB of all-zero pages the bound if written-zero pages are counted in. F403, F443 and Q21
  stay open.
- Not answered: the cost of a large PRT or read-only span in page tables; whether the ring reset succeeds under
  the title's own load.

### 56. Fifteen minutes of play on the shared build without the learned file (2026-11-13 04:59–05:17)

The top session's order after the integration (shared normal build `fe0933c0`, patch 4651d1d3 = main 7d21b208, with
the three mr412 switches compiled in and off). Run s1nol: `run0412n.sh s1nol fast8 900 BC5_GUARD_LEARN_LOG=1` with
`N_EMU` = the shared binary (the runner's new `N_SHARED_MD5` check), an **empty** private learned file, RT on, the
private copy of the named save snapshot, fuse 13,000/2,048, watchdog 220 MiB, the shell running, no rsync, the
kernel log streamed. It follows one recovered ring reset in the same boot (E1 case 4, 04:56:58; `raw/s1nol-header.txt`).
Data `raw/s1nol-*`.

[M] It reached G+900: 1,017 s, 900 s of play on the scripted walk, **no kernel line, no GPU fault or timeout, no
"would learn" line, the private learned file still empty**; 25.8 flips/s over 1,013 s, 87 s with a gap over 100 ms,
the longest 681 ms; lowest available 402 MiB, highest PSI full 5 %; pinned direct 11,440 MiB at the end. The shared
learned and alias files kept their checksums.

**Reading.** With sections 52 and 53 that is four runs and 2,039 s of this route without the learned file and without
a fault, one of them 15 minutes long and on the shared build. It is evidence for the route, which stays in one area
of the game; his own play (the pause menu, Photo Mode, the lake, fights) is where the windows were learned and is
not covered by it.

### 57. The smaller memory offer (12,800 MiB): what is on record, and the catcher that is missing (2026-11-13, laptop only)

The top session's order: option A's largest unknown. A read of the records (a sub-agent's search over this branch
and the main checkout, HEAD 4178a97a; I have not re-read every line it cites). `P` is patch 0001.

**How the offer is set** [C]: `KYTY_GUEST_MEMORY_MB`, read once in `PhysicalMemory::TotalSize()` (P:21142); unset,
the code's own value is the console's 12,800 MiB, capped by host RAM. Today's 13,824 comes from the launchers.
`KernelGetDirectMemorySize` reports total minus flexible memory; the AMM auto pool borrows from that same direct
memory when the title's pool is full (P:38832–38845).

**Every recorded run with less than 13,824** [M, from the experiments' own files]:

| offer | when, where | what happened | judged |
|---|---|---|---|
| 12,288 | exp 0330 arm D, 10-25 | stops 3 s after start: `condition (g_tls_main_program == nullptr)` in `runtimeLinker.cpp:1470` | "why it fails was not read further" |
| 11,776 and 12,288 | 11-06 | "died at startup in the title's TLS setup": cited second-hand in exp 0409 only; no primary record found | none |
| 12,460 (`MEMORY_FROM_PARAM`) | exp 0401 e2, 11-03 | play "very smooth but short"; host fatal `AMM virtual-memory unmap is unsupported` at 145 s, right after `auto pool exhausted: map of 0x4000000 bytes refused` | **ours** (a refused AMM borrow) |
| 12,800 | exp 0409, 11-09, 5 runs | 5 of 5 died at 159–195 s: that fatal, or a host write into the unmapped AMM window (access violation at `runtimeLinker.cpp:1166`) | **ours**, the same class |
| 12,800 + `KYTY_BC5_AMM_SCATTER=rescue` | exp 0409, 11-09, 7 runs | 4 of 7 reached G+600; 3 froze about 3 min after G with no log and no kernel line and exited 133 (SIGTRAP) | not known (a title int3 or a host trap) |
| 12,800 | his play, 11-10 | exit 65 at 106 s in the load: access violation, write into the AMM window | the 11-03 class |

**Two classes, then.** (1) **Start deaths at 12,288 and below** (3 s in, the main program's TLS): never read
further; one primary record. (2) **Deaths in the load or early play at 12,460–12,800**: the host's AMM auto pool
cannot borrow direct memory and the host then faults or gives up: **our defect**, not the title's reaction; exp 0409's
`rescue` removes the load fatal and leaves an unexplained SIGTRAP in 3 of 7.

**Exp 0413's set-buffer bug as a cause** [I]: all of these runs predate its guard (in the shared builds since
11-12 18:02). It is a candidate for class (1) only by its nature (a page of the title zeroed by chance, depending on
the binary and what a register happens to hold); against it, the second title took that call's "map flavour" 0 times
in 2,304 calls of a 180 s trace. It does not explain class (2), which the trace lines tie to refused borrows. Nobody
has run a smaller offer since the guard: one start at 12,288 on today's shared build answers it in 10 seconds.

**How large the lever really is** [M, exp 0409]: at 12,800 the GTT maximum was only **190–220 MiB lower** than at
13,824, and his 11-10 play at 12,800 still showed about 12.5 GiB of GTT. So the "about 1 GiB" of the offer does not
arrive as 1 GiB less pinned: the title reserves 12,162 MiB at 13,824 and whether it sizes its heaps from the offer is
not measured (README section 16, HANDOFF F622/F625 call it "not a lever" for that reason). Worth having if it costs
nothing, but it is a 0.2 GiB item on the evidence, like the shell.

**The catcher that is missing** (proposal; not built). Today a run at 12,800 says where it died, not which host call
first went wrong. One private build on the shared tree, switches default off:
1. `KYTY_BC5_MEM_FIRSTFAIL=1`: the first time ANY memory call of the host returns an error to the title or refuses
   internally (allocate/map/reserve direct, flexible, pooled, the AMM borrow and scatter, `mmap` fixed over a live
   range), one journal line: the call, its arguments, the error, the caller's guest return address and thread, and
   the state then: direct total, allocated, largest free hole, flexible used, the AMM pool's maps and free bytes.
   Later failures are counted, not printed.
2. `KYTY_BC5_TRAP_LOG=1`: a SIGTRAP handler that journals rip, the thread's name and the guest module of the address,
   then lets the default action happen (exp 0401 proposed it; it names the int3 of the `rescue` runs).
3. The existing `KYTY_BC5_AMM_TRACE=1` and the set-buffer guard's own line stay on in those runs.
Runs (his slot, RT on, the scripted route): 12,288 once (10 s: is the start death still there after the guard?);
12,800 without and with `rescue`, three each, stop at the first kernel error. The answer wanted is one line: the
first failing call and the pool state, per class.

### 58. What asks the kernel for compaction (kcompactd0's 80–100 s per run): a read of the sources (2026-11-13, laptop only)

The top session's order, after exp 0415's numbers and section 53's (kcompactd0 80 and 100 s of CPU in a 4-minute
run, kswapd0 8–12 s; more with every emulator start since boot). Nothing measured here. Sources: Linux v6.19
(`drivers/dma-buf/udmabuf.c` read whole; the `mm/` files through a fetching sub-agent, whose quotes are marked
[V] verbatim or [S] from its summary of a part it did not get verbatim: **[S] lines are unverified**), and the local
copies of `ttm_pool.c`, `ttm_tt.c` used for the design study. The box runs 7.2: TODO(verify) against its source.

**Who can wake kcompactd.**
1. **kcompactd by itself: proactive compaction.** [V] `sysctl_compaction_proactiveness = 20` by default; every
   `HPAGE_FRAG_CHECK_INTERVAL_MSEC` (500 ms) the thread asks `should_proactive_compact_node()`, which is false while
   kswapd runs and otherwise true when the node's fragmentation score **at huge-page order** is above the high mark
   (`fragmentation_score_wmark`: low = 100 − proactiveness = 80, high = 90); it then compacts until the score is
   under 80. [S] When the score does not fall it backs off (`timeout << COMPACT_MAX_DEFER_SHIFT`, 6: 32 s). No
   allocation of ours is needed for this: a machine whose free memory is scattered between pinned pages has a high
   score all the time.
2. **kswapd, on every pass.** [S] `balance_pgdat()` ends with `wakeup_kcompactd(pgdat, pageblock_order, ...)` and
   `kswapd_try_to_sleep()` with the order kswapd was woken for. At the wall kswapd runs continuously (README
   sections 16, 53), so kcompactd is woken continuously with the page-block order, whatever we ask for.
3. **High-order requests on our import path** [V unless marked]:
   - `udmabuf_create`: four arrays of one pointer or offset per page, `kvmalloc_array`/`kvcalloc` with `GFP_KERNEL`:
     a temporary `folios`, then `ubuf->folios`, `ubuf->offsets`, `ubuf->pinned_folios`. For a 64 MiB buffer (16,384
     pages, the module's default `size_limit_mb = 64`) each is **131,072 bytes: an order-5 request** before
     `kvmalloc` falls back to vmalloc ([S] `kmalloc_gfp_adjust`: above a page it adds `__GFP_NOWARN` and drops
     direct reclaim unless `__GFP_RETRY_MAYFAIL`; the request can still wake kswapd, and through it kcompactd).
     `vmap_udmabuf` makes a fifth. For a 2 MiB buffer the arrays are 4 KiB: order 0.
   - amdgpu's import: `ttm_sg_tt_alloc_page_directory`: `kvcalloc(num_pages, sizeof(*ttm->dma_address), GFP_KERNEL)`,
     again 131,072 bytes per 64 MiB BO (local `ttm_tt.c:138`).
   - `sg_alloc_table(sg, pagecount, GFP_KERNEL)` per buffer: chained page-sized pieces, order 0 [I].
   - GPU-owned memory (page tables of the GPU VM, the driver's buffers): `__ttm_pool_alloc` starts at
     `MAX_PAGE_ORDER` and walks down; for order > 0 it adds `__GFP_NORETRY | __GFP_NOWARN | __GFP_NOMEMALLOC`, and
     above the device's "beneficial order" it drops direct reclaim (local `ttm_pool.c:149–158, 738`). Every miss
     at a high order can wake kswapd.
   - Pinning: [S] `memfd_pin_folios()` runs `check_and_migrate_movable_folios()` in a retry loop: folios that may not
     be pinned long-term (ZONE_MOVABLE, CMA) are migrated first. The box has no CMA (`CmaTotal 0`, section 50's
     snapshot); whether it has a movable zone is not known [TODO(verify): /proc/zoneinfo].
4. **THP**: `enabled` is madvise, shmem never, `AnonHugePages 0` in every snapshot: nothing asks on our behalf [M
   for the settings and the zero; that no library madvises is not checked].

**Reading [I].** Two of the three sources need nothing from us: with 12 GiB pinned and unmovable, the huge-page
fragmentation score is high for good, so the proactive thread and every kswapd pass send kcompactd to scan for
pages it cannot move. That also fits the growth with boot age: each emulator start pins 12 GiB in a new pattern, the
free pages left between runs are scattered over more page blocks, and the scans get longer for the same result.
Our own part is the order-5 arrays: with imports made 2 MiB at a time, merged into 64 MiB buffers later and cut
again by the orphan release, a run makes thousands of them (two to five per buffer per cycle). They do not cause
the scanning, but each can start one.

**How to tell them apart, read-only** (no root beyond what the sampler already has): per phase, the deltas of
`/proc/vmstat` `compact_daemon_wake`, `compact_daemon_migrate_scanned`, `compact_daemon_free_scanned`,
`compact_stall`, `compact_fail`, `compact_success`, `pgmigrate_success`/`_fail`, `kswapd_low_wmark_hit_quickly`,
`pageoutrun`; `/proc/buddyinfo` at the phase's start and end (free blocks of order 9 and above); the value of
`/proc/sys/vm/compaction_proactiveness`; kcompactd0's and kswapd0's CPU as exp 0415 already samples. A run of the
shared build with the merge pass off (2 MiB buffers only, if a switch exists: TODO(verify)) against one with it on
separates our arrays from the rest.

**What could change, and who decides.**
- `vm.compaction_proactiveness = 0` for the time of a play removes source 1. It is a system-wide setting: **his
  decision and his command**, not ours (no sysctl changes by a session). The cheapest experiment there is: one
  value, undone by writing 20 back.
- Our path: make each heap's buffers **once, at their final size** when the title maps the heap, instead of
  2 MiB → merge → cut. Fewer order-5 requests and far fewer create/import/free cycles; but "final size at map
  time" is R1, which pins what is never written (section 53). With option B's read-only cover the two fit
  together; not before.
- A hugetlb memfd (udmabuf accepts it: `check_memfd_seals` allows `is_file_hugepages`) would end fragmentation for
  the guest's memory, at the price of 12 GiB of huge pages reserved up front by the system and never swappable:
  his decision too, and the opposite of what the wall needs. Not proposed.

### 59. The catcher kit for the smaller offer and for compaction (tag ff412; laptop only, not built)

The top session's order after sections 57 and 58 ("fixes first"). Written against the **shared tree** rebuilt on the
laptop (upstream KytyPlus f266548 + the integrated patch 4651d1d3; `memory.cpp` eff24b4c and `libAmpr.cpp` a2d09d32
match the integrator's list). `memfast/mkff0412.py` edits four units; every anchor is asserted once; outputs:
`memory.cpp` 961da63a, `libAmpr.cpp` d88da83d, `hostException.cpp` e978e975, `bc5LleAgc.cpp` d8270884. The diff is
in the shared notes (`exp0412-ff412-units.diff`, 550 lines). **Nothing of it has been compiled**: the laptop cannot
build these units; the first compile is the box's.

| switch (all default off) | what it does |
|---|---|
| `KYTY_BC5_MEM_FIRSTFAIL=1` | 18 memory calls of the host (allocate, release, map, reserve, protect, batch map, the pool calls, flexible map, munmap, the available-size query) are wrapped: a non-OK result is counted and the first 12 and every power-of-two-th are written in full: the call, the result, up to six arguments, the caller's address, the thread, and the direct memory's state (offered, free, runs, the largest run; flexible configured and available). The AMM auto pool's refused borrow is noted with the pool's maps, free bytes and largest free run; a failed AMM command with its kind, address and size. Before the exit on an access to a reserved AMM page the last 8 failures are printed. A catcher: no result changes |
| `KYTY_BC5_TRAP_LOG=1` | a SIGTRAP is journaled (rip, rsp, thread), then takes its default action as before (exit status 133): it names the int3 of exp 0409's `rescue` runs |
| `BC5_DIRECT_MAX_BO_MIB=<n>` | the largest import, never above the udmabuf module's own limit. With 16 the kernel's per-buffer arrays are 32 KiB (order 3) instead of 128 KiB (order 5): the test of section 58's source (iii) |

CPU test `firstfail0412.cpp` (which failures print, the ring of the last eight against a model): 101,506 of 101,506
on the laptop. `compact0412.sh`: the read-only collector of section 58's counters (kcompactd0 and kswapd0 CPU, the
compaction, migration and kswapd counters of `/proc/vmstat` as deltas, free blocks of order 9 and 10, available
memory), one line every 5 s beside a run; syntax-checked only.

**The fix candidate for class (b) is already in the shared tree** ([C] for each piece of code, [I] for the chain between them): the death at 12,460–12,800
is one thing: the AMM auto pool keeps contiguous runs (first fit) and, when no run fits, borrows a contiguous range
of direct memory; when that is refused `MapAuto` returns EAGAIN, "the buffer stops here", the title goes on, and the
next access to that address (the host's own APR read copying into it, or the title) hits a reserved AMM page, where
`KernelHandleReservedRangeAccessViolation` exits with the misleading text "AMM virtual-memory unmap is
unsupported". The pool was not empty then (212 MiB free on 11-03), only fragmented. The console's pool maps
scattered pages (AnyPS5, cited in `libAmpr.cpp`), which is what `KYTY_BC5_AMM_SCATTER=rescue|first` (exp 0409)
does. So no new fix is written: the runs test `rescue` and `first` with the catchers on, and the catchers say what
the 3-of-7 freeze under `rescue` is. A host that survives a truly empty pool (failing the title's call instead of
dying) is not written: I do not know the console's error for it (TODO(verify)).

**Order-5 arrays: how often, and can they be reused** [C][I]. They live in the kernel, one set per udmabuf and per
imported BO; user space cannot reuse them. They are made on every `import_memfd`: a first import of a filled chunk
run, every merge (the merged buffer is a new udmabuf, the old ones are freed), and every cut by the orphan release
(the surviving pieces are imported again). Only buffers above 16 MiB make requests the kernel calls costly (above
order 3). How many imports of which size a load makes is not counted in my data; exp 0415's `ls415_import` counter
has it per phase. **Exp 0415's counts** [M, its runs r6n1 and r6n2, build L5b, RT on; first imports and merges are
counted together]: movies (33 s) 181 and 167 calls, 10.0 and 9.7 GiB, mean 57–59 MiB; menu load (13–15 s) 261 and
280 calls, 4.8 and 5.7 GiB, mean 19–20 MiB; start screen and menus 19 and 7 calls; save load 22 and 23 calls,
mean 56–80 MiB; play (64 s) 64 and 74 calls, 3.0 and 3.4 GiB, mean 47–48 MiB: about one call a second. In all about
**550 imports and 21 GiB imported for a footprint of 12 GiB up to one minute of play**: every byte is imported about
1.8 times (first as it fills, again when merged), and by the mean sizes most calls are above 16 MiB, so most make
the costly-order arrays: on the order of 2,500 such requests a run [I, 5 arrays a call]. The candidates are: (1) `BC5_DIRECT_MAX_BO_MIB=16` (above): four times the buffers, each
with order-3 arrays; the price is a longer BO list per submission; (2) no merge-then-cut: buffers made once at
their final size, which needs the final size known at map time (R1 or option B).

**Runs asked for** (one slot, RT on, the scripted route, stop at the first kernel error; a private build of the four
units on the shared tree, the shared builds untouched): the offer 12,288 once (10 s: is the start death still there
after exp 0413's guard?); 12,800 with `KYTY_BC5_AMM_SCATTER` unset, `rescue` and `first`, each with FIRSTFAIL,
TRAP_LOG and `KYTY_BC5_AMM_TRACE=1`; and at 13,824 one pair `BC5_DIRECT_MAX_BO_MIB` unset against 16 with
`compact0412.sh` beside each.

### 60. The learned windows are out of the second title's launchers (2026-11-13 08:16–08:22)

The maintainer's order, relayed verbatim by the top session: "masz się pozbyć wyuczonych okien! to jest coś chorego
[...] to jest obejście a potrzebne jest rozwiązanie, które softwareowo gdzieś jest". It covers his shortcut and the
shared launchers; no variant that keeps the file is offered again.

**What was changed on the box** [M]:
- **His shortcut:** `play-guard-0412.sh` has the arm `fast9` (`eb4feddc`; the old one kept as
  `play-guard-0412.sh.before-fast9-a547d77c`): fast8's words on the **shared** normal build `fe0933c0`, the launcher
  derived with one line changed (the learned file's path, to the empty `exp0412/learned-none.txt`), and
  `BC5_GUARD_LEARN_LOG=2`: the catcher journals a GPU fault as "would learn ..." with its address and kind, **writes
  nothing and adds nothing, not even for the run** (mode 1 would keep a window for the run, which is a remembered
  window again). fast8's words read the same before and after (78), fast9 adds two. The desktop has "BC5 emulator
  (0412 fast9 bez Plasmy)" (the shell is still stopped for the play); the fast8 shortcut is in
  `~/bc5-work/trash-20261113/pulpit`.
- **The shared launchers** (`nolearned0412.sh`): `play-pkg.sh` 157021e3 → **47426d8e**, `play-pkg-log.sh` 5080d2ce →
  7d33409f, `play-pkg-quiet.sh` 48fa60ba → 4230882c: the one `export BC5_DIRECT_LEARNED=…` line became two (the path of
  the empty read-only `~/bc5-work/direct-learned-none.txt`, and `BC5_GUARD_LEARN_LOG=${BC5_GUARD_LEARN_LOG:-2}`). Each
  old file is beside as `<name>.before-nolearned`; `bash -n`; the diff is that one line.
- **The learned file** `direct-learned-pkg.txt` (81 lines, cb30371e) was moved to `~/bc5-work/trash-20261113/`, not
  deleted. `run0412n.sh` no longer needs it (its default source is an empty file).
- Still naming the old file: `run-pkg.sh` (its default when `LEARNED` is unset), `play-pkg-exp0155.sh`,
  `lean-backup-play-pkg.sh`; with the file gone they read nothing, and a fault there would **create it again**
  unless `BC5_GUARD_LEARN_LOG` is set. Not changed (not in the order). ASTRO BOT's launcher names no learned file,
  but the code's default path `~/bc5-work/direct-learned.txt` exists and is read when the variable is unset: also not
  changed; the top session decides.

**Shown to run** [M]:
- fast9's words on the shared build, the scripted route to gameplay (run f9a, RT on, fuse and watchdog as always):
  G+60 reached, 177 s, 28.1 flips/s, no kernel line, no "would learn" line, lowest available 503 MiB; the old file
  was not created again.
- `play-pkg.sh` with a stand-in for the emulator (it prints its environment and exits; no game, his log and saves
  untouched): the emulator would get `BC5_DIRECT_LEARNED=…/direct-learned-none.txt` and `BC5_GUARD_LEARN_LOG=2`.
  `play-pkg-log.sh` and `play-pkg-quiet.sh` ended with status 1 before they reached the stand-in (they do not take
  it); they are checked by `bash -n` and by their one-line diff only.
- **Not done:** a start of `play-pkg.sh` itself to gameplay. It runs on his live save directory, which a session
  does not start a game on; the shortcut itself (with the shell stopped) has not been started with the game either.

**What it means in play.** A place the windows used to cover is now a GPU fault: a 14 s stall with a "would learn"
line naming the address and its kind, **every time that place is met in the run**, since nothing is added. If one
scene faults on every frame it will not get past that scene until the cause is fixed in code. Each such line is a
bug report (README section 61 will hold the rules by kind); none becomes a window.

**Undo** (his word only): copy the three `.before-nolearned` files back, move the learned file back from the trash
directory, and put the fast8 shortcut back from `trash-20261113/pulpit`.

### 61. The learned path out of the unit (tag nl412), the K1 catcher, and the second remembered list (2026-11-13, laptop; not compiled)

**nl412** (`memfast/mknl0412.py`, on the shared unit a81efd2c of patch 4651d1d3; sent to the integrator). The top
session chose the variant `--keep-guards`, output `cfb7533e`:
- **gone:** the learned file's read (also the code's default path, which ASTRO BOT used) and write, the list
  `g_learned`, `learned_add()`, `map_window()` (forcing a past fault's chunks and mapping anonymous memory in its
  window), and the zero fill of the windows' holes;
- **always on:** the catcher: a GPU fault is journaled as "would learn ..." with what lay at its address; nothing is
  added and nothing is written; `BC5_GUARD_LEARN_LOG` no longer decides it;
- **kept, and why (the top session's words):** the 2 MiB zero guard behind each eager heap is a rule from the title's
  behaviour (it reads up to 64 KiB past its GPU heaps' ends, exp 0037), applied to every such heap from the layout,
  with no memory of a fault; what the maintainer rejects is the remembered list. Its proper form is the K3 rule
  (the console's behaviour over true holes), and the guard goes when that rule is in. All my runs without the file
  (2,216 s) had the guards active; the variant without them (`b91669e0`) has never run.
- one journal line at the first submission says the path is gone.

**The K1 catcher in the same unit**: `BC5_GUARD_K1_STAT=1` (default off, no behaviour change). For every new target
base the hint path sees (colour, depth, stencil, HTILE) it journals whether the 2 MiB chunk at the base itself was
imported when the title bound it, and how much the ±32 MiB window around it then pinned; a summary every 64 bases.
It measures how far today's guess is from the rule "import exactly what the title binds, when it binds it"
(`DESIGN-learned-windows.md` section 7).

**The second remembered list: the aliases** (`BC5_DIRECT_ALIASES=1` in the launchers, `~/bc5-work/direct-aliases-pkg.txt`,
written on 10-22 and not since; it was active in all my runs). Five lines "byte, window start, 96 MiB" [M, read
today], each mapped a second time at (byte << 40) + address **over whatever is mapped in the window**:

| line | what it is | source |
|---|---|---|
| `0x80 0x11ce000000` | the one real alias: the title's programs (0x11d0…) are fetched at 0x80 11d0…: dozens of its programs call through function pointers loaded from its constant buffers, and those pointers carry 0x80 in bits 47:40 | exp 0056, F110 (the fault went, hangs followed; TODO(verify) there: whether the console's GPU ignores those bits or maps code there too) |
| `0x80 0xc8d2000000`, `0xcc 0x580a000000`, `0xdb 0x3252000000`, `0x80 0x906000000` | no guest memory lies in any of these windows (the title's heaps are at 0x10…–0x14… and the AMM window at 0x80…): they map nothing. They are faults at junk addresses learned before exp 0195 added the test "the low 40 bits must name guest memory"; one of that kind (0x80 over 0–96 MiB) is what exp 0195 found and removed | exp 0195; F251, F253: 0x80 in `COMPUTE_PGM_HI` there was another process's register left on the shared GFX ring, not the title's tag |

So the list is one rule and four dead lines. **The rule that replaces it** [I]: an alias is not two guest views of one
physical range (the host would know those at map time); it is the title's own code reached through pointers that
carry a tag byte. What the title tells the host before use is the program addresses themselves (it sets them in the
program registers of every draw and dispatch): the view that holds a bound program is the title's code heap, and
"map the code heap a second time under 0x80 when it is mapped" is a rule from the layout, with no memory of a fault.
The four junk lines need no replacement (they are K4). Before the list is removed: (1) which view the programs lie
in and its size (one line of a journal), (2) one run with the list reduced to its first line, (3) the rule in code.
Not removed today, on the top session's word.

**Where the 0x80 comes from is not established** (the top session's question: a fixed property of the console's GPU
address space, cited, or read off this title?). It is read off this title: exp 0056 saw this title's function
pointers carry it; F110 left "the PS5 GPU ignores those bits or maps code there too" as TODO(verify). I looked for a
public statement and found none: the references on the laptop treat a guest GPU address as 48 bits, a 40-bit base in
units of 256 bytes with an 8-bit extension register (AnyPS5 @ 27c88a8d75ca,
`core/libs/prx/libSceAgcDriver/Graphics/src/GuestTextureResource.cpp:57-66`; KytyPlus
`src/graphics/guest_gpu/command_processor/pm4Handlers.cpp:1000, 2648`), which says the bits exist, not that they
are ignored. So a rule may not hard-code 0x80 or a heap address on today's knowledge. What settles it, read-only and
without a new fault: (1) the tag byte of every function pointer in one of the title's constant buffers that hold
them (the catcher's K4 line already prints what lies under the low 40 bits of a tagged fault address); if every
code pointer of the title carries the same byte and nothing else does, the tag is a format of the pointer (to be
looked for in the public shader-binary and AGC descriptions, `refs/OpenProspero_AGC`), and the rule is "the range
that holds bound programs is also reachable with that format's byte"; (2) a second title's pointers (ASTRO BOT runs
without aliases: either it has no such calls or its pointers carry no tag). Until then the one real line stays as it
is and is named for what it is: a remembered alias.

**Stale launchers that still name the old learned file** (for the cleanup; not called by anything current as far as
a search of `~/bc5-work/*.sh` and the desktop shows: TODO(verify) on the box before they move): `run-pkg.sh`,
`play-pkg-exp0155.sh`, `lean-backup-play-pkg.sh`.

### 62. His first play without the learned file: one fault, classified (2026-11-13 08:54–09:02; observed read-only)

He started "BC5 emulator (0412 fast9 bez Plasmy)" himself; this session only watched (a `pgrep` every 10 s, then
reads after the emulator had ended). Journal `~/bc5-data/captures/play-20261113-0854/gc/direct.log` (on the box; the
two dumped buffers beside it are the title's and are not committed).

[M]
- The emulator had `BC5_EMU` = the shared build, `BC5_DIRECT_LEARNED=…/exp0412/learned-none.txt`,
  `BC5_GUARD_LEARN_LOG=2`. The shell was stopped at 08:54:37 and started again at 09:02:01 by the lean watcher
  (plasmashell 0 during the play, running after it): **the lean session's first real run worked**.
- The emulator lived 441 s. **Corrected (the top session's facts, 09:10): the play did not go on after the fault.** He
  was in an in-game cutscene; after the fault and the reopen the picture stayed frozen while the emulator ran on
  (sound, 289 % CPU); the top session ended it with SIGTERM at 09:02, which is the "exit 0". My first reading of
  "reopen: ok" and the later ledger lines as "the play went on" was wrong. At the last ledger line (430 s): pinned
  direct 11,764 MiB, available 873 MiB, PSI full 0.7 %.
- **One GPU fault, at 285.9 s**: address **0x1100000000**. The kernel: client SQC (data), `PERMISSION_FAULTS: 0x3`,
  **`RW: 0x0`: a read**. Ring timeout 2.0 s later, `Ring gfx_0.0.0 reset succeeded`, the host's "reopen: ok"; the
  title did not recover (see the correction above and "After the reopen" below). Two submissions timed out together (a draw buffer of 32,485 dwords and a compute
  buffer of 32,335), both passed by the operand filter with `unmapped 0`.
- The catcher's line: **K1, under a BY-DATA view, chunk never written by the CPU**: view `AssetHeap Large` (direct,
  by data; 604 of 816 MiB of that heap were pinned at the end), chunk not imported, no GPU mapping, a guest range
  yes. The window it would once have learned, 0x10fe000000+96 MiB, is one of the old file's 81 lines (HANDOFF F779 and
  F781 record it being learned): the file did cover this place; the scripted route never goes there.
- The old learned file was not created again; nothing was added.

**Is 0x1100000000 exp 0346's fallback window?** [C][M] It is the same number, and for a reason: 0x11 is the high
half of the title's 4 GiB window, which exp 0346's switch (`BC5_DIRECT_HOST_INDIRECT=learn:1100000000`) uses as the
base for a GFX-form indirect dispatch that carries no `SET_BASE`, "until one is learned", where "learned" means read
from the title's own `SET_BASE`s during the run (`backend/src/direct.cpp:558`), not from the learned file. But this
fault was not that path: the kernel names the client **SQC (data)**, a shader's data fetch, not the command
processor reading dispatch arguments, and 0346 rewrites a dispatch only to a page the host itself could read and
NOPs it otherwise, so it sends no reader to an unmapped page. What the two share is the address: the first page of
the title's window, where `AssetHeap Large` begins. A shader that follows a 32-bit pointer or offset of 0 inside
that window reads exactly there [I]. The learned file did not feed 0346's base; it kept this page mapped (its line
0x10fe000000+96 MiB forced the heap's first chunks), and without it the page was unmapped.

**The indirect dispatch with the garbage grid (dword 40,954 of the compute buffer)** [M][I]. The probe marks every
dispatch and every label write of the compute buffer #229185 as DROPPED: that buffer did not run. Its indirect
dispatch at 40,954 takes its arguments at 0x1187497000+0xe00; the count the probe printed is what that memory held
at the timeout, and since the jobs that would have produced it were lost with the reset, garbage there is expected
and comes **after** the fault, not before it. Nothing here shows F403's shape (a dispatch that never ends): the
fault came first, in a shader's read.

**After the reopen: why the picture froze** [M][I]. The lost compute buffer ends in label writes that the title
waits for, among them a counter at 0x11e1024040 (to become 0x21c71; it stayed 0x21c70) and a flag at 0x11e0ec0018
(to become 1; it stayed 0). The probe counts 14 label writes in that buffer; e11's recovery line says "0 label
writes of the lost jobs: ... 0 written (BC5_DIRECT_RESET_LABELS on)". So the labels of the lost job were never
written and the title waits on them for ever. That is a defect of ours in the recovery (the reset-labels code did
not find the lost job's writes), apart from the mapping question: with it, **every** recovered fault in such a
frame freezes the title, whatever caused the fault.

**Why e11 saw 0 of the 14 label writes: read in the code** [C], and the fix candidate (tag rl412, not built).
`m11_keep_lost()` copies the list of pending label writes at a timeout; it is called once for every timed-out job
(the unit's completion loop), and each call is followed by `forget_label_writes(..., all)`, which empties the list.
Here two jobs timed out in the same hang (#229185 and #229186): the first call kept both jobs' writes, the forget
emptied the pending list, and the **second call copied the empty list over what had been kept**. The reopen then
found "0 label writes of the lost jobs" and wrote nothing. Every one of the four hangs on record with a draw and a
compute buffer timed out together (F260, sections 38 and 53, this one) goes through the same two calls [I: only this
one has e11's line]. `memfast/rlabels0412.inc`, `mkrl0412.py`: **`BC5_DIRECT_RESET_LABELS_ADD=1`** (default off): a
second keep for the same reopen adds to the kept list instead of replacing it, and journals what it did. CPU test
`rlabels0412.cpp`: 4,970 of 4,970 on the laptop (the two-timeout case with the switch off reproduces the empty
list; on, the first call's writes survive). On the shared unit a81efd2c the edit gives `1ae28d7c`; on nl412's
keep-guards unit `0878903e`. Whether the title then goes on is not known: the labels are written, the lost job's
work is not done (design section 8.2's question); it is the smallest thing between "a fault" and "a freeze".

**What kind of miss this is, and its rule** [I]. The GPU **read** (a shader's data fetch) a 2 MiB chunk of a heap
that the title mapped and the CPU had never written. Its content is zeros: the read was legitimate and its right
answer was zero. The learned window answered it by pinning 96 MiB around the address for ever; "import at bind
time" (K1 as section 7 states it) does not fit either, because the address did not come from a register the host
parses (the filter saw nothing unmapped): the shader computed it or took it from a table. This is the case E1
measured: **a never-written chunk under a view can be mapped read-only onto the zero BO**: this read then returns
zero with no fault and no pinned page (E1 case 2), and if the GPU ever writes there instead, the fault names it
(E1 case 4). So the first real sample asks for exactly the cover of design section 8 (option B's read side), not for
a window and not for a bind-time import. It also says what that cover must be under: views imported by data
(`AssetHeap`, `InitAllocator`, the small heaps), chunk by chunk, switched to the real page when the CPU first writes
(the `SEEK_DATA` pass already sees that).

**The rule to build next** (kind "K1r", a read of a never-written chunk): in the mapping rebuild, every chunk under
a non-eager view that is not imported is mapped **readable only** onto the shared zero BO; when the chunk gets
data it is imported and the real mapping replaces the cover (the rebuild already does that order for the pin cap's
cover, `guard0412_want`, which maps the same zero BO read-write today). A write fault there is journaled with its
address and is then a K1 bind-time case. Behind a default-off switch first; its test is this very place in his
play (his save, about 285 s in).

### 63. K1r, the read-only zero cover, and the one build that carries everything (2026-11-13, laptop; not compiled)

**K1r** (tag k1r412: `memfast/k1r0412.inc`, `k1r0412.cpp`, `mkk1r0412.py`): `BC5_GUARD_K1R=1`, default off in the
test build and meant to become the default. Every part of a view of direct memory that no imported buffer covers
(a chunk the CPU never wrote, in a heap imported by data or lazily) is GPU-mapped **readable only** onto one shared
2 MiB zero buffer of its own; nothing is pinned for it. In the code:
- the mapping rebuild's want list gets the cover's pieces after the real mappings (`k1r412_want`); a piece never
  exceeds a chunk and never crosses a chunk boundary of the file, so a chunk's later import replaces whole pieces;
- a piece is mapped through a new backend call, `Device::map_shared(..., bool readonly)` (`AMDGPU_VM_PAGE_READABLE`
  alone). **The backend changes**: `direct.hpp` and `direct.cpp`, 33 lines of diff; the test build uses a private copy
  of the backend source and its own archive, the shared archive is only read;
- a rebuild that changes the set of buffers replaces covers by real mappings (unmap, then map), so it now drains the
  GPU first (`wait_jobs`), as a rebuild that retires buffers does. That is a new cost at every import (about 550 a
  run, section 59) and the first thing to measure;
- the fault path journals a fault under a cover as its own kind: a **write** is "K1w" (the job is lost; the cure is
  the bind-time import of that target, which `BC5_GUARD_K1_STAT` counts), a read there is reported as a defect;
- every 10 s at most the zero buffer is read back through a read-only CPU view and a non-zero word is journaled
  ("IT MUST BE ZERO"); it cannot happen through the GPU, since no mapping of it has the write bit;
- the cover is refused when the zero skip or the pin cap is set (they map their own buffer there), and it acts on
  the direct-memory file only.

The four points asked for, as the unit and its test have them:
- (a) **ordering**: the CPU's first write is seen by the import's `SEEK_DATA` pass at the sync before a submission;
  the chunk is imported and the same rebuild drops the cover and maps the real pages before that submission reaches
  the kernel. Relied on: the title writes its data before it submits what reads it, and the sync runs before every
  submission. A chunk written since the last sync is zero for the GPU until that sync; without the cover it was a
  fault, never the data;
- (b) a GPU **write** into a cover faults by name (E1 case 4), is journaled as K1w, and loses the job;
- (c) an address under **no** view gets nothing and stays loud (the test: no page outside the view is covered);
- (d) the zero buffer is shared and read-only for the GPU, so nothing can be written or aliased through it; the
  test checks the pieces (exactly the uncovered pages of the view, each once), the code maps them only through the
  read-only call, and the read-back catches the impossible.
CPU test `k1r0412.cpp`: 17,742 of 17,742 on the laptop (a page-level model of a file, its imported ranges and a
view, 3,000 layouts; after "the CPU writes one chunk" exactly that chunk's pieces go and every other piece is
unchanged; the write bit of the two kernel status samples).

**The console's behaviour for K1r** [I]: on the console memory the title mapped exists for the GPU from the map call
on, and reads as zero until something writes it; a GPU read of such memory is ordinary. That is inferred from the
title's own map calls and from this fault (the title's shader reads there in normal play); I have no console trace
and no public document that states it.

**The second form: `BC5_GUARD_K1R_REPLACE=1`** (default off; the top session's order, written before any measurement).
A real mapping that takes the place of covers is mapped **over** them with one `AMDGPU_VA_OP_REPLACE`
(`Device::map_shared_over`, new in the backend: it accepts the range only if every shared mapping in it lies wholly
inside, and takes those out of its list), and the rebuild does **not** drain the GPU for it; the drop pass leaves such
covers mapped until the real mapping goes over them. What it is and is not, from the driver's code (v6.19
`amdgpu_gem_va_update_vm`: `amdgpu_vm_clear_freed` and then `amdgpu_vm_bo_update` in one ioctl) [C]: one ioctl, but
still two page-table updates in order, the old entries cleared and then the new ones written. The hole a running
job could meet shrinks from "between two ioctls" to "between two updates in the kernel"; it is **not shown to be
zero**. With `BC5_FAULT_RECORD` a job that meets it ends the game with a record, so the comparison of the two forms
has to count faults as well as the drain's time. The backend diff is now 83 lines (`direct.hpp` 26519fcc,
`direct.cpp` 8f617378 from this branch's 51279eae); it is a shared change decided yes by the top session, for the
integrator to rebuild the archive from when the tests are clean.

**rl412's risk, and what e11 decided** [C]. Exp 0401's e11 chose that at "reopen: ok" the last pending write of each
label of the jobs in flight goes to guest memory, unless memory already holds it or the label lies in no guest
range. That tells the title "this work happened" for jobs whose GPU work did not run: the frame's picture or
compute results can be wrong or stale for that frame, and a title that reads results back gets old data. The
alternative, not writing them, is the freeze he saw. rl412 does not change that decision; it only makes it hold
when two jobs time out together, which it did not (section 62). Whether the title's next frames repair the lost
frame's state is what the test at the cutscene measures.

**One build with everything** (`memfast/mk0412z.sh`, build g412z, binary beside as `bin-z`): from the shared tree's
unit a81efd2c the chain nl412 `--keep-guards` (cfb7533e) → rl412 (0878903e) → k1r412 (0d265595) → fr412 (ce3be3a7) → ff412 (2961feac),
with `memory.cpp` 961da63a, `libAmpr.cpp` d88da83d, `hostException.cpp` e978e975, a private backend with
`map_shared(readonly)`, and the four CPU tests first. Every sum is pinned in the script. Switches, all default off:
`BC5_GUARD_K1R`, `BC5_GUARD_K1R_REPLACE`, `BC5_FAULT_RECORD`, `BC5_DIRECT_RESET_LABELS_ADD`, `BC5_GUARD_K1_STAT`, `KYTY_BC5_MEM_FIRSTFAIL`, `KYTY_BC5_TRAP_LOG`,
`BC5_DIRECT_MAX_BO_MIB`, `BC5_GUARD_MAP_RULE`, `BC5_GUARD_PRT_BG`. **Not compiled anywhere yet.**

**Tests in the top session's order**: (a) the place of his fault, K1r on (expected: no fault there, the read
returns zero), then K1r off with rl412 on (expected: the fault, a recovered reset, the labels written; whether the
title then goes on is the measurement); (b) the scripted route to G+240 with K1r on: regressions, the pin, the cost
of the extra drains; (c) the budget runs of section 59; (d) `e1-probe` case 6 last.

### 64. The rule after his play: a fault is a bug at its source; the fault record, the register, the cutscene arm (2026-11-13; laptop, not compiled)

The maintainer, on the label write-back (rl412): "i znowu robimy obejście dla problemu? czy jest szansa ze ps5 dziala
tak samo?" and his rule: "Każdy błąd GPU traktujemy jako błąd do usunięcia u źródła, a nie coś, po czym gra ma się
podnieść. zapis diagnostykę dla siebie, aby usunąć źródło błędu w kolejnym podejściu". The console has no such fault
and does not resume a title after a GPU hang; e11's write-back is a net for our own bugs. So:

- **rl412** (`BC5_DIRECT_RESET_LABELS_ADD`) stays default off and is no fix: one diagnostic arm at most. No recovery
  variant is offered again. **K1r is the fix** for his cutscene and the only priority.
- **The fault record** (tag fr412, `memfast/mkfr0412.py`): `BC5_FAULT_RECORD=1` (default off in the test build, meant
  to become the default). At the first GPU fault or ring timeout the emulator writes one self-contained directory
  under `~/bc5-data/captures/faults/<date-time>/` and **ends the game** (exit code 86, one stderr line naming the
  record): no reopen. In it: `record.txt` in words (when, the address and status with read or write, the catcher's
  kind, the view or heap and whether its chunk was imported and GPU-mapped, the pin, the capture directory with the
  journal and the dumped buffers), `journal-tail.txt` (the last 4 MiB: the probe's summary of the timed-out jobs,
  the last submissions, the ledger, the frame lines), the layout (`layout-views.txt`, `layout-buffers.txt`,
  `layout-mappings.txt`), `meminfo.txt`, `pressure.txt`, `environment.txt` (every `BC5_*` and `KYTY_*` variable),
  `process.txt`. What the emulator cannot read (the kernel's own lines, the devcoredump's path, the binary's md5)
  the launcher is to add after the exit; that launcher step is not written yet. Nothing in a record is read by a
  later run. Limits: the exit is abrupt for the title (a save being written at that instant could be cut short).
- **The register**: `FAULTS.md` beside this file, one row per fault with its kind, root cause, rule, how the console
  behaves (with a source, or marked inferred) and status. Row 1 is today's cutscene fault.
- **The build** (`memfast/mk0412z.sh`) now chains nl412 keep-guards (cfb7533e) → rl412 (0878903e) → k1r412 with the replace form
  (0d265595) → fr412 (ce3be3a7) → ff412 (2961feac). Not compiled.

**The cutscene arm.** His answer: "ostatni zapis - przerywnik od razu się uruchamia". A new read-only snapshot of his
live saves as they were after the play: `~/bc5-data/saves/PPSA03671-20261113-0914-cutscene` (131 files, 23 MiB, the
list `files.md5` d26b3608; the copy compared equal to the source; no emulator of his ran; nothing is ever written
back). By time the newest is **slot 4** (autosave and its snapshot written 08:58 today, during the play, before the
fault at 08:59; slots 1–3 are of 11-03, 10-22 and 11-01). `run0412n.sh` got three options, defaults unchanged:
`N_SAVES=<dir>` (the private working copy is reset from that snapshot), `N_SLOT=<n>` (n−1 presses of down before
the cross on the slot list: the list is walked by position, and whether the title lists slot 4 fourth or first is
to be seen in the first run), `N_NOWALK=1` (no input after the load). The arm: start, menu, slot 4, Continue, no
input, 240 s.

### 65. The fault record must not cut a save: the save guard; the launcher's step (2026-11-13; laptop, not compiled)

The top's condition before `BC5_FAULT_RECORD` can become a default: the maintainer plays on his live saves, and a
diagnostic exit that cuts a save would be worse than the freeze. The title's saves go through our own host calls,
so the host knows when one is being written.

**The save guard** (tag sg412: `memfast/saveguard0412.inc`, put into the tree as `src/bc5/save_guard0412.hpp` by
`memfast/mksg0412.py`; the wait is called from the fault record only). "A save being written" is a marked host call
in flight, or a save mount (`/savedata<n>`) that has been written since it was mounted and is not unmounted yet
(the title mounts, writes its files, unmounts). Before exit 86 the record now:

1. lets a save that is being written go on to its end, **5 s at most**; nothing new starts in that time (a first
   write on a clean mount, a new mount, a writing call of the save-data library: the caller is held and never
   returns);
2. then holds every marked call, flushes the streams and syncs the file system of the save directory (`syncfs`);
3. writes into `record.txt` whether a save was in flight at the request, how long the wait took, what was left, and
   the sync's outcome; when the 5 s were not enough the words are "A SAVE WAS BEING WRITTEN AND DID NOT FINISH IN
   THE TIME ALLOWED: THAT SAVE MAY BE INCOMPLETE", also on stderr.

Marked calls: in `src/kernel/fileSystem.cpp` open (a write, create or truncate open counts as a write), close,
write, pwrite, ftruncate, truncate, fsync, unlink, rename, mkdir, rmdir, only for names under a save mount; in
`src/libs/libSaveData.cpp` the mounts, the unmount, delete, the save-data memory's set and sync, the parameters, the
icon by path. Without a fault nothing is held or changed: a marked call costs two atomic adds. A second thread that
reaches the record while the first writes it is held (one record per run).

**CPU test** `memfast/saveguard0412.cpp` with a stand-in writer (mount, four parts, close, unmount) and close() as the
stand-in exit: 178 of 178 on the laptop (three runs; 20 rounds each of A–D). A: the exit asked for in the middle of a
write: the file is complete; B: between two writes of one save: complete; C: mounted, nothing written yet: untouched,
the writer's first write held; D: before the mount: untouched; E: a writer that never finishes: the bound holds and
the outcome says the save may be incomplete (the one case where a half file stays, and it is named); F: after the
close every marked call is held; G: no close, nothing held; the path parsing; the draining rules.

**Limits, said plainly.** (1) The guard knows saves by the host's calls. If the title keeps a save mount open for a
long time after writing it (not seen yet: its autosave pattern is to be read from the first record's line "the last
save call began … ms before"), every exit would wait the full 5 s and report an incomplete save falsely; then the
rule needs a quiet-time clause. (2) A save is several files; the guard waits for the unmount, it does not make the
set atomic: a fault more than 5 s before the title would have finished still leaves a part. On the console that
set is made atomic by the system's save-data transaction [I: from the library's Prepare/Commit calls, which this
host answers without doing anything; no console trace]. (3) Not compiled; the first build is g412z.

**The launcher's step** `faultrec0412.sh <start> <binary> [<dmesg lines at the start>]`: after a run it completes every
record written since the start that has no `build.txt`: `dmesg.txt` (the kernel log since the start),
`dmesg-gpu.txt` (its amdgpu, drm, fault and reset lines), `build.txt` (the binary's path, md5 and time; kernel, Mesa,
libdrm; the kernel's verdict in one line with the fault lines; the devcoredump's path, waited for 20 s at most).
It ends by itself; it leaves no waiter. `run0412n.sh` calls it after every run. A dry run on the laptop with
stand-ins (a fake record, a fake kernel log) completed the record and did nothing the second time. Not yet in his
shortcut's launcher: that follows the first clean test and his word.

**The build's sums now** (`memfast/mk0412z.sh`, kit `kit-z.sha256`, 16 files): nl412 cfb7533e → rl412 0878903e → k1r412
0d265595 → fr412 with the guard's call df69ba22 → ff412 169bd1df (as first written; as built: section 66); sg412: fileSystem.cpp 9194fc38 → 3d2b9c0b,
libSaveData.cpp 0e0c5d40 → 090e32cb, the header 1f1585b4. Five CPU tests in the build script.

### 66. g412z built; the cutscene arm three times: clean with K1r, and clean WITHOUT it (2026-11-13 09:56–10:21, box)

**The build.** `mk0412z.sh`: the five CPU tests pass on the box (firstfail 101,506, maprule 15,281, rlabels 4,970,
k1r 17,742, saveguard 178). The first compile failed in one place of mine: the save guard's header was included
inside a namespace in `libSaveData.cpp` (and would have been in the main unit, where it would also have made a second,
separate set of the guard's counters); both includes moved to the files' top level. Second compile: **g412z
`e07e3414`**, 64 warnings, private backend archive 4c340f6d; the shared tree, builds, backend and archive only read.
Sums as built: main unit nl412 cfb7533e → rl412 0878903e → k1r412 0d265595 → fr412 0a4fa422 → ff412 1c5d1ec2;
fileSystem.cpp 3d2b9c0b, libSaveData.cpp 0bd91bb4, the header 1f1585b4; backend direct.hpp 26519fcc, direct.cpp 8f617378.

**The arm** (`run0412n.sh`, `N_SAVES` = the snapshot of 09:14, `N_SLOT=4`, `N_NOWALK=1`, arm fast8's words plus
`BC5_GUARD_LEARN_LOG=2 BC5_GUARD_K1_STAT=1 BC5_FAULT_RECORD=1`, RT on, fuse 13,000/2,048, 240 s after the load with no
input). The slot list is walked by position; the title wrote `i38-slot4-game-autosave` in the runs where it could
write, so the fourth entry is his slot 4 [M].

| run | K1r | ended | flips/s | kernel lines | fault record | pinned direct max, lowest available |
|---|---|---|---|---|---|---|
| k1ra 10:01 | on | G+240, 354 s | 29.7 | 0 | none | 11,248 MiB, 685 MiB |
| k1rb 10:08 | on | G+240, 355 s | 29.9 | 0 | none | 11,250 MiB, 727 MiB |
| k1rc 10:14 | **off** | G+240, 356 s | 30.5 | 0 | none | 11,234 MiB, 970 MiB |

(f9a this morning, the scripted walk on the shared build: 11,424 MiB and 501 MiB.) All three passed the 286th second,
the time of the morning's fault, with 25–34 flips/s around it.

- **K1r in k1ra** [M]: 942 read-only zero pieces over 1,870 MiB at the first rebuild; 512 pieces over 1,020 MiB at
  289 s (about 430 pieces gave way to real pages as the CPU wrote them); the zero buffer held 0 non-zero words at
  every one of the 12 checks; no line of a GPU write into a cover; the drain counted 0 in the journal's last timing
  windows. Covers pin nothing: the pin is the same with and without them. The replace form was not run.
- **The maintainer watched k1ra at the box** (relayed by the top; his observation of the picture, not a
  measurement): "Bardzo stabilna gra była".
- **k1ra ran on a read-only save copy** (my defect: `cp -a` kept the snapshot's read-only modes, the title could not
  write; the next start failed on `rm`). Fixed in `run0412n.sh` (the private copy is made writable); k1rb and k1rc
  ran with it and the title wrote its autosave.

**What this does and does not show.** The control did not fault. So on this route **the morning's fault is not
reproduced, and the two clean K1r runs do not show that K1r removes it.** K1r is shown only to run: 710 s of this
scene with about 1 GiB under read-only zero covers, no fault, no write into a cover, the speed and the memory of
the control. The fault record and the save guard were armed in all three and never called: untested in the real
build. Why the control is clean is not known. Candidates [I]: (a) the morning's state came from four minutes of his
play before the scene (the autosave of 08:58 was written in that play, the fault came a minute later), and a load
straight into the scene lays the heap out differently; (b) the fault depends on what the scene does after an input
of his; (c) it is intermittent (one control so far). The K1 catcher's line carries a defect of mine (an unsigned
underflow prints "17592186044412.0 MiB" for the windows' total in k1ra): the number is wrong, nothing depends on it.

### 67. The morning's page, watched and read by the host: with K1r it reads zero (2026-11-13 10:25–10:45, box)

The top's order after section 66: do not wait for chance; make the test deterministic at the address.

**Two more controls** (K1r off, the same arm): k1rd on g412z, 354 s, 30.1 flips/s, 0 kernel lines; k1re on g412za,
354 s, 30.3, 0 kernel lines. Three controls in all, none faulted.

**The watched address** (tag wa412, `memfast/mkwa0412.py`, `BC5_GUARD_WATCH=<hex>[,<hex>...]`, a catcher, default
unset; build **g412za `c4bb0bff`** = g412z + it). For each address the journal says, at every change and every 10 s:
the view over it, whether the CPU has written its 2 MiB chunk of the direct file (SEEK_DATA), whether the chunk is
imported, and what the GPU has there (no mapping, the title's memory, a read-only zero cover). Read on the
submitting thread at the start of the per-submission sync.

k1re [M], 0x1100000000 and 0x1100200000, from the first line to 350 s, never changed: under "AssetHeap Large" (by
data; view 0x10d0000000+0x33000000, the address 0x30000000 into it; file chunk 0x91a00000): **the chunk never written
by the CPU, not imported; GPU: NO MAPPING**. So the page is in the state of the morning's fault for the whole run:
the route is not past it. The title does not read that page in these runs (three controls), which is why they are
clean. Why it read it in his play is not known (candidates in section 66).

**The host's read probe** (tag pr412, `memfast/mkpr0412.py`, `BC5_GUARD_K1R_PROBE=<hex address>[,<seconds after the
emulator's start>]`, default unset; build **g412zb `65511824`** = g412za + it, first compile clean; private backend
direct.hpp 2497a4ce, direct.cpp b183516e, archive ed63df2f). Once, at the first submission after the time,
`Device::probe_read` submits jobs of the host's own **in a context of its own** (the title's context and its state
are not touched; the address space belongs to the device file, so it is the title's): IGT's gfx10 buffer-copy
program, as in `e1/e1-probe.cpp` (cited there), copies 16 KiB from a source to the probe's destination, which the
host fills with 0xA5 first. Step 1 is a control (the source is the probe's own pattern; if it does not arrive whole
the probe says it is not working and stops); step 2 journals the address's state; step 3 is the read. One 64 KiB
buffer at 0xFDFF000000; a command slot is used once (E1's finding); at most four probes per run. No CPU test (it
is a GPU job); the unit chain is nl412 → rl412 → k1r412 → fr412 0a4fa422 → wa412 5d763ab8 → pr412 dfa98a48 → ff412
9d4de45e.

**k1rf [M]: K1r on, the probe at 0x1100000000 at 200 s** (g412zb, the same arm, `BC5_FAULT_RECORD=1`):

- the control ran in 2.04 ms and all 16,384 bytes matched the pattern;
- the address before the read: under "AssetHeap Large", the chunk never written, not imported; **GPU: a read-only
  zero cover (K1r)** (the watch shows the cover from 0.9 s on);
- **the read ran in 0.03 ms: all 16,384 bytes zero, none of the destination's fill left; no fault**;
- the run went on to G+240 (357 s, 30.6 flips/s), 0 kernel lines, no fault record.

**What this shows.** On the page of the morning's fault, in the title's real layout and in the state the fault had
(never written, not imported), a GPU read with K1r on returns zeros and does not fault. That is K1r's rule shown at
the address, by a read of ours, not by the title's shader. **What it does not show:** the same read without K1r
faulting in this build (E1's cases and the morning's fault say an unmapped page faults; the probe's own arm for it is
a deliberate GPU fault and waits for the maintainer's word), the fault record, the save guard and exit 86 in the real
build (they have still not fired), and the title's own read of that page (not reproduced).

**Limits of the probe.** It reads 16 KiB (four pages) from the address, not 16 bytes. Its job is on the GFX ring in
another context: it says what the address space returns, not what the title's shader would have done with zeros.
The control's line counts 128 bytes "still holding the fill": those are pattern bytes that happen to equal 0xA5.

### 68. The replace form; the one deliberate fault: the read without K1r faults, the record is written, exit 86 (2026-11-13 10:46–11:11, box)

**k1rg [M]: K1r's replace form** (`BC5_GUARD_K1R=1 BC5_GUARD_K1R_REPLACE=1`, g412zb, the probe at 200 s): G+240, 355 s,
30.0 flips/s, 0 kernel lines; the probe's control whole, the address under a read-only zero cover, **the read
16,384 zero bytes, no fault**; 942 pieces at the first rebuild, 516 at 177 s, the zero buffer 0 non-zero words. The
journal's drain figures do not separate the two forms (k1rf: 1,674 drains counted, k1rg: 1,482; the timing line's
drain is for every rebuild, not K1r's alone), so the replace form is shown to run, not to be faster. Whether its
two page-table updates can be met by a running job (section 63) was not seen and is not excluded by one run.

**k1rh [M]: the deliberate fault.** The maintainer's word, relayed by the top, to the question "may the guardian
trigger ONE deliberate GPU fault (K1R off, the probe reading 0x1100000000) to test the fault record, the save guard
and the clean exit, with the risk of a reboot if the reset fails; private save copy only": "Tak, wywołaj". One run:
g412zb, K1r off, `BC5_GUARD_K1R_PROBE=1100000000,200 BC5_FAULT_RECORD=1`, the private save copy, the kernel log
polled every 10 s.

- The probe at 200.0 s: the control whole; the address "never written by the CPU, not imported; GPU: NO MAPPING";
  **the read timed out after 2,055 ms: fault address 0x1100000000, status 0x00701031 (a read)**.
- The kernel: page faults at 0x1100000000–0x1100003000 (the probe's four pages), client TCP, `PERMISSION_FAULTS 0x3`,
  `RW 0x0`; ring gfx_0.0.0 timeout; **ring reset succeeded**; "device wedged, but no recovery needed"; the gpu-watch
  armed and disarmed 5 ms apart. No reboot (up since 00:11). Devcoredump `20261113-111017-devcd3.txt`.
- **The fault record** `~/bc5-data/captures/faults/20261113-111017/` (never committed): `record.txt` names the time
  (202.056 s), the address and status as a read, the kind "K1 under a BY-DATA view, chunk never written by the CPU",
  the view ("AssetHeap Large", by data, 0x10d0000000+0x33000000, the address 0x30000000 into it), the chunk not
  imported, no GPU mapping, the pin (11,250 MiB in 69 buffers; 15,378 mappings), the capture directory; with it the
  journal's tail (4 MiB), the three layout files, meminfo, pressure, environment, process.
- **The save guard's line in it:** "no save was being written when the game was ended. At the request: 0 save
  call(s) of the host in flight, 0 save mount(s) written and not yet unmounted, the last save call began 9775 ms
  before. Waited 0 ms; … Sync of the save directory: done." So the guard was called, found nothing in flight, and
  synced. **The case of a save in flight at the fault has still run only in the CPU test.**
- **The exit:** one stderr line naming the record and the saves' state; the emulator's exit code 86; the launcher's
  exit 86; no emulator left, the lock released, plasmashell running. `run0412n.sh` ended the arm at "ring reset
  succeeded at 203 s" and called `faultrec0412.sh`, which added `dmesg.txt`, `dmesg-gpu.txt` (33 lines) and
  `build.txt` (binary 65511824, the kernel's verdict "a page fault, a ring timeout, reset succeeded" with the fault
  lines, the devcoredump's path). A defect of that step: Mesa's and libdrm's versions are printed twice in one
  line (two packages answer the query); the versions themselves are right (kernel 7.2.15-ogc1.1, Mesa 26.2.6-2,
  libdrm 2.4.134-2: newer than CLAUDE.md records).

**The pair at one address, in the title's real layout** [M]: the same page, the same state (never written, not
imported), the same read by the same program: **without K1r a fault** with the morning's kernel words (address,
`PERMISSION_FAULTS 0x3`, `RW 0x0`; the morning's client was SQC (data), the probe's is TCP: another shader stage);
**with K1r, in both forms, 16,384 zero bytes and no kernel line**. That is the rule shown to remove this fault
class at this address. Still not shown: the title's own read of the page (not reproduced on the scripted route),
and what the title does with the zeros (in his play of the morning the learned window had given it zeros there
for weeks, section 62).

**For the shared build** (the top's order): K1r on by default, the fault record on by default, rl412 off, the
replace form off, the probe and the watch compiled in and off. `memfast/mkdef0412.py` flips the two defaults in the
final unit ("0" turns each off): 9d4de45e → 417616db. Not built or run with the flipped defaults; **K1r has never run
on ASTRO BOT**, which the shared build also plays: that run is owed before or with the fold.

### 69. K1r faulted ASTRO BOT's start and the box rebooted: a cover was visible to the host's packet filter (2026-11-13 11:32; the fix written, not compiled)

**What happened** (the integrator's run, exp 0417, candidate 26ef195c with K1r and the fault record on by default,
nothing set; its report, not my measurement): ASTRO BOT faulted 3.8 s after the start, the ring reset **failed**, the
gpu-watch rebooted the box at 11:32:18. The fault record fired (`~/bc5-data/captures/faults/20261113-113217`, without
the launcher's files: the box went down first): fault 0x3082f6000, status 0x00640c41 (a **write**), under the lazy
view "orbis_user_malloc" (0x3018c0000+0x11d30000), the chunk not imported, a GPU mapping at the address: yes (the
cover); the journal's own line "under the read-only zero cover: a GPU WRITE (kind K1w)"; 2,615 covers over 5,230 MiB
at 1 s. The same start is clean without K1r.

**This is a defect of mine in K1r**, and section 68's last sentence named the gap it came through: K1r had never
run on ASTRO BOT.

**Cause** [I: from the code and the status; the record's journal is not read yet]. The status' client field is 6,
CPG in the kernel's gfxhub client table (today's other two statuses decode by the same table to 8 = TCP and 10 =
SQC (data), which the kernel printed in words): the **command processor** wrote, so it was a packet's write, not a
shader's. The unit asks "is this address mapped?" with one function, `covered_sorted()` over the device's mapping
list, in 49 places; the first of them is the packet filter's operand check (a packet whose operand is unmapped is
dropped). A cover is a shared mapping in that list and was reported as an ordinary writable one. So with K1r on,
never-written memory under a view looked mapped to the host: the filter let a packet through that it had always
dropped, and the command processor wrote into a read-only page. Lazy views import only what the bind hints force
(`direct_sync_one`: `if (v.lazy) continue`), so that chunk was not imported in the clean runs either: **before K1r
the title's write was silently dropped by the filter**. My five K1r runs on the second title did not meet such a
packet, and I had not asked what else reads the mapping list.

**The rule.** A cover exists for the GPU's own reads (a shader's, as in his cutscene). For every decision of the
host it is a hole, as that memory was before K1r. Then with K1r on the host behaves exactly as without it and only
the GPU's page tables differ: a shader's read of never-written memory returns zeros instead of faulting; everything
else is as it was. It is not "no covers under lazy views": a shader's read of a lazy heap's never-written chunk is
the same case as the cutscene's.

**The fix** (tag cv412, `memfast/mkcv0412.py`, no switch of its own: it is part of K1r). Backend: a shared mapping
keeps whether it was mapped readable only, and `Device::mappings()` / `sorted_mappings()` report it (before, a
shared mapping was always reported writable). Unit: `covered_sorted()` and `covered()` do not count a mapping that
is shared and read-only (only covers are). Sums on my chain: after pr412 dfa98a48 → cv412 ec17e59f → ff412 5706511b;
backend direct.cpp b183516e → 1d88a8b3, direct.hpp 2497a4ce unchanged. Build script `memfast/mk0412zc.sh` (g412zc,
`bin-c`, kit of 19 files). **Not compiled, not run.** No CPU test of its own (two one-line conditions).

**What stays wrong and is older than K1r:** the filter drops a packet that writes into never-imported lazy memory,
so that write of the title is lost. The console has that memory (the title mapped it). Its rule is the import of a
packet's write target when the packet is seen (section 61's K1, "exact bind-time import", for packets). Registered
in `FAULTS.md` as an open item that is not a fault.

**Owed before K1r is a default again:** g412zc built; the second title's cutscene arm with the probe (the read must
still return zeros: the probe is the backend's own job and does not pass the filter); ASTRO BOT's start with K1r;
the scripted walk. The default stays off until then.

### 70. The record of ASTRO BOT's fault read; K1 at the filter written (2026-11-13; laptop, not compiled)

**The record** `~/bc5-data/captures/faults/20261113-113217` and the devcoredump `20261113-113218-devcd4.txt`, read
with the top's GO (files only) [M]:

- the fault: 3.756 s after the start, 0x3082f6000, status 0x00640c41 (a write; client field 6); thread DrawThread;
  under "orbis_user_malloc" (lazy; view 0x3018c0000+0x11d30000), the chunk not imported, a GPU mapping there (the
  cover); pinned 2,468 MiB in 21 buffers, 5,120 mappings;
- the job: **submission #58, a draw buffer of 10,494 dwords** ("pass 830 rewrite 287 drop 259 **unmapped 0**"),
  timed out after 2,359 ms; the next submission was refused;
- the devcoredump: ring gfx_0.0.0; `CP_IB1_CMD_BUFSZ` 0x49f8 with `CP_IB1_BUFSZ` 0x3f98 left (the command processor
  stood 2,656 dwords into a first-level buffer); `CP_IB2_BASE` 0x800100015000, `CP_IB2_CMD_BUFSZ` 0xa8, 0 left (it had
  run a second-level buffer of 168 dwords to its end); the page fault at 0x3082f6000 with status 0x640c41;
- the run wrote no dump of the buffer (the fault record ends the game before the timed-out job's dump), so **which
  packet wrote is not read from the run**.

**What that confirms and what it does not.** Confirmed: the write came from the command processor's side (the
status' client 6, CPG in the kernel's table) while it ran a draw buffer; the filter counted **no** unmapped operand
in that buffer, with 5,230 MiB of never-written memory reported as mapped. Not confirmed from the run: that
without K1r the filter counts an unmapped operand in the same buffer and drops the packet (that line needs a run
without K1r with the journal not quiet), and which packet it is. A second reading fits the same facts: a
host-inserted helper (the backend's indirect-argument check asks `opt.mapped(va, 12)` before it adds its own
packets, some of which write) that was not added before because the address was not mapped. Both are the same
defect, a host decision that took a cover for the title's memory, and cv412 removes both. Old journals in this
repository show the drops are common without K1r (for example a draw buffer of 3,257 dwords with "drop 200
unmapped 52").

**The top's point, and it is right:** cv412 only restores the state before K1r, and that state drops a packet in
which the title tells the command processor to read or write memory it mapped. On the console that memory exists
and the access lands. The packet names its operand, so the host knows the address before the GPU touches it.

**K1 at the filter** (tag k1f412, `memfast/mkk1f0412.py`, `BC5_GUARD_K1_FILTER=1`, default off). Before the sync of
each submission the unit walks the buffer's type-3 packets and their memory operands (`bc5::policy::
memory_operands`, the list the filter itself checks); an operand that is not mapped gets its chunk(s) imported at
once (`direct_force`: real pages, mapped), so the filter then passes the packet. The journal names the first 200
firings and every 256th after (the buffer's kind, the packet's opcode and place, the operand, the megabytes
imported) with the totals. Limits: only the buffer handed to the submission is walked, not the second-level buffers
it names (the backend filters those; ASTRO BOT's fault had just left one); an operand under no view stays unmapped
(the K3 case); every import pins memory, and that price is not measured; the walk's time under the device mutex is
not measured. Needs cv412 when K1r is on.

**The build** `memfast/mk0412zc.sh` (g412zc, `bin-c`, kit of 22 files) now chains … pr412 dfa98a48 → cv412 8269b175 →
k1f412 609b0f58 → ff412 063f9ad4; backend direct.cpp 1d88a8b3. **Not compiled.** After the top's word ("each with its
switch, CPU tests first") cv412 got both: the rule lives in `memfast/cover0412.inc` (`cv412::hole`), is on by default,
and `BC5_GUARD_K1R_COVERS_VISIBLE=1` turns it off (the state that faulted, kept only to tell the two apart); CPU test
`memfast/cover0412.cpp`, 640,008 of 640,008 on the laptop: with the rule the answer is the same as on the mapping list
with the covers removed (the host behaves as before K1r); the operand of 11:32 under a cover is not mapped with the
rule and mapped without. K1 at the filter has no CPU test (its decision is that same function; the rest is the
import call). The maintainer's word for the ASTRO BOT start with K1r on, relayed by the top, to "if the reading is
wrong the box may reboot again: do you agree to this test?": "Tak".

**The order of the cure for row 1 (his cutscene) without harming ASTRO BOT:** cv412 always with K1r (K1r then cannot
change any host decision); K1 at the filter beside it, measured for its imports and time on both titles; K1r's
default stays off until ASTRO BOT's start and both titles' routes have run with it. Covers stay under lazy views:
with cv412 a cover there changes nothing for the host, and a shader's read of a lazy heap's never-written chunk is
the cutscene's case. What neither does: a **shader's write** into never-written memory under a cover still faults
(as it faulted before K1r, unmapped). Its rule is the import of the write targets the title binds (render targets,
depth, RW buffers and images in the descriptors): the bind hints do the first two today, the descriptors are not
read.

### 71. Build g412zc on the box: what the filter drops, K1r with cv412 on ASTRO BOT, K1 at the filter; a new K1r defect under lazy views (2026-11-13 15:13-15:42, box)

Build g412zc (`memfast/mk0412zc.sh`, kit `kit-zc.sha256`): binary a927b6fa, private backend archive 4c5bb4fc, the
six CPU tests passed on the box. The first run of the script stopped at its own string check ("tag cv412" is only in
comments, never in the binary); the check was removed and the script run again (same binary). Six arms, all [M],
none with a kernel amdgpu line, no reboot. `BC5_DIRECT_TIMEOUT_PROBE=1` and `BC5_FAULT_RECORD=1` in all. ASTRO BOT
through exp 0413's `start0413g.sh` with `PLAY_CAPTURE=1` on a fresh private save directory (the integrator's was
moved to `wda/_SaveData.aside-0412-1520`); the second title through `run0412n.sh`, arm fast8, the cutscene snapshot,
slot 4, no input, 240 s, fuse 13,000/2,048, watchdog 220. Raw files on the box: `~/bc5-work/exp0413/n/raw/zc*` and
`~/bc5-work/exp0412/night/raw/zc*`; journals `~/bc5-data/captures/play-20261113-15{16,30,33}/gc/direct.log`.

| arm | title, switches | result |
|---|---|---|
| zc1alog | ASTRO BOT 60 s, `K1_FILTER=log`, K1r off | ran 60 s; 17,886 unmapped operands by 51 s: op 0x49 14,905 (11,924 under a view), op 0x93 2,981 (none under a view); 3 pages named |
| zc2log | second title, `K1_FILTER=log`, K1r off | G+240; 23,084 unmapped operands by 352 s: op 0x49 10,459, op 0x93 12,615, op 0x9f 10; **none under a view** |
| zc3k1r | second title, `K1R=1`, watch and probe at 0x1100000000 | G+240; the probe at 200 s: 16,384 zero bytes, no fault (as k1rf: cv412 changed nothing here); 516-518 covers over 1,028-1,032 MiB |
| zc4k1r | ASTRO BOT 120 s, `K1R=1` (cv412 alone) | ran 120 s, no fault (the start that faulted at 3.8 s and rebooted the box at 11:32); 2,876-3,747 covers over 5.8-7.5 GiB |
| zc5k1f | ASTRO BOT 120 s, `K1R=1`, `K1_FILTER=1` | ran 120 s; ONE import, 2 MiB at 1.271 s (the chunk of 0x3082f6f60); "now mapped" |
| zc6k1f | second title, `K1_FILTER=1`, K1r off | G+240; 0 imports (as zc2log predicts); 29.9 flips/s, GTT 11,578 MiB at 352 s (zc2log: 29.9, 11,579) |

**What the filter drops in ASTRO BOT [M].** The dcb of 10,494 dwords (the size of the 11:32 record's submission #58)
carries, at dwords 1883 and 1891, two packets of opcode 0x49 whose operands are 0x3082f6f60+8 and 0x3082f7060+8:
the page of the 11:32 fault, under "orbis_user_malloc" (lazy), chunk not imported. So the packet that faulted with
visible covers is named: with K1r's covers visible the filter let these two through and the command processor wrote
into a read-only page. Without K1r they are dropped about 230 times a second (CORRECTED in section 72: a dropped
packet is executed by the soft CP on the CPU; the write is not lost, it is made by the host).
With `K1_FILTER=1` one 2 MiB import ends that. The third page, 0x7fc0a4269000 (op 0x93), is a host address under no
view: not memory of the direct file, so not K1's case. Not decoded here: what opcode 0x49 and 0x93 are in the
title's stream (TODO(verify): the packet names against the public PM4 headers before they are written as fact).

**What the filter drops in the second title [M]:** nothing under a view. K1 at the filter is ASTRO BOT's cure, not
the second title's; there it costs nothing and changes nothing (zc6k1f).

**A new defect of K1r, found by the watch (zc4k1r, zc5k1f) [M]:** at 0x3082f6000 from 0.5 s on: "the chunk WRITTEN by
the CPU, not imported; GPU: a read-only zero cover (K1r)". K1r covers every part of a view that no imported buffer
covers (`k1r412_want`), and `k1r0412.inc` says such a part is never-written memory because "the import's SEEK_DATA
pass sees data, the chunk is imported". That holds under a view imported by data. Under a LAZY view only hints
import, so a chunk the CPU has written stays unimported and got the zero cover: a GPU read there would return zeros
where the title's data lies. No such read was seen (the title's packets there are writes), so this is a defect by
reading the code and one watched page, not a wrong picture observed.

**The fix written: kl412** (`memfast/kl0412.inc`, `kl0412.cpp` 99,003 of 99,003 on the laptop, `mkkl0412.py` after
`mkk1f0412.py`: unit 52319499, after `mkff0412.py` 90c1129b; build script `mk0412zd.sh`, kit `kit-zd.sha256`, bin-d;
NOT compiled, NOT on the box). Under a lazy view a piece whose file chunk holds data gets no cover: it stays unmapped
as without K1r, and a GPU read there is a fault with a record that names it. `BC5_GUARD_K1R_COVER_WRITTEN=1` turns
the rule off. The file is asked (SEEK_DATA, once per piece) at a mapping rebuild and at most every
`BC5_GUARD_K1R_WRITTEN_SCAN_MS` (default 100); the journal gives the count and the time. Limits: a chunk written
since the last scan keeps its cover until the next rebuild after the period; and a hole is the honest state, not the
cure: the console lets the GPU read written memory, so the cure for a read of written lazy memory is its import
(K1 at the filter does that for the operands packets name; shader reads are not known in advance).

Not done: the arms on g412zd; the second title's walk route and his own play with any of this; a decode of the
packets; the defaults (K1R stays off by default).

### 72. Build g412zd on candidate B: kl412 on both titles, the price of importing written lazy memory, whose the "no view" operands are; a correction to section 71 (2026-11-13 16:24-16:47, box)

**Correction to section 71.** "The title's write is lost each frame" was wrong. A packet the filter drops is not
lost: the soft CP runs after every submission and executes each packet that did not run on the real GPU
(`execute()` in the unit: `done = gpu_packet_done(...)`, then `release_mem(p, len - 1, !done)`, `if (!done)
wait_reg_mem(...)`, `if (!done) write_data(...)`), so a dropped RELEASE_MEM's value is written by the host's CPU and
a dropped WAIT_REG_MEM is waited for on the CPU [read in the code, not measured]. What differs from the console is
WHEN and BY WHOM the value is written (by the host after the submission returns, not by the GPU at the end of the
pipeline). The packet names, from `backend/src/policy.cpp`'s table: 0x49 RELEASE_MEM, 0x93 WAIT_REG_MEM64, 0x9f
LOAD_CONTEXT_REG_INDEX. So K1 at the filter in ASTRO BOT moves two label writes a frame from the host's CPU to the
GPU for 2 MiB of pin; it does not restore a lost write.

**The base.** The shared tree is candidate B since 15:47 (patch 0001 27b6416f, unit 8126c0aa; it carries nl412,
rl412, fr412, sg412, ff412). `memfast/mk0412zd.sh` was rewritten for it: the private tree is brought to the shared
tree's state (rsync, .git left), then six scripts on the shared unit, each sum checked against the laptop's:
mkk1r 4bd99863, mkwa f27b793e, mkpr 5edc7f4c, mkcv 74412dc8, mkk1f 150c5d89, mkkl 393a0cbf; the backend as in g412zc
(archive 4c5bb4fc). Binary **be507cd5** (bin-d); CPU tests k1r0412, cover0412, kl0412 passed on the box. mkkl0412.py
also adds `BC5_GUARD_LAZY_BY_DATA=1` (default off): `direct_lazy_name()` answers "no", so `BC5_DIRECT_LAZY_NAMES` is
ignored and those views are imported by data like every other. This IS the top's variant (b), "import a written
chunk of a lazy view at the CPU's write": no new mechanism, the lazy list is what keeps such chunks out today.

Four arms, all [M], no kernel amdgpu line, no reboot; `BC5_GUARD_K1R=1 BC5_GUARD_K1_FILTER=log BC5_FAULT_RECORD=1
BC5_DIRECT_TIMEOUT_PROBE=1` in all. Small raw files: `raw/zcd/` (also section 71's).

| arm | title | written chunks under lazy views (kl412) | GTT | result |
|---|---|---|---|---|
| zd1k1r | ASTRO BOT 120 s | 366 (732 MiB) get no cover; 2,510 covers over 5,020 MiB | 7,263 MiB at 45 and 100 s | ran 120 s; the page 0x3082f6000 "WRITTEN, not imported; GPU: NO MAPPING" from 0.5 s |
| zd2bydata | ASTRO BOT 120 s, `LAZY_BY_DATA=1` | 0 (all imported) | 7,995-7,999 MiB: **+734 MiB** | ran 120 s; the page imported at 1.4 s; the two RELEASE_MEM operands no longer dropped |
| zd3k1r | second title, cutscene arm, probe | 110 (220 MiB) get no cover; 406 covers over 808 MiB | 11,614 MiB at 285-326 s (peak 11,974) | G+240, 29.6 flips/s; the probe: 16,384 zero bytes |
| zd4bydata | second title, cutscene arm, `LAZY_BY_DATA=1` | 0 | 11,808 MiB at 284-326 s (peak 12,188): **+194 MiB** | G+240, 30.2 flips/s; lowest available memory 749 MiB; the sampler's last column 74 against 0 (swap, as I read it) |

**kl412 [M]:** with the rule the written chunks of lazy views are uncovered on both titles and nothing faults in
these arms, so in these 120 s and 240 s no GPU read touches them. The scan costs 0.84-1.1 ms each, 3-5 a second
(650 ms over 212 s in the second title: 0.3 % of one core). In the second title the covers shrink from 1,028 to
808 MiB: 220 MiB of what K1r called "never-written" held data.

**The price of the general rule (variant b) [M], one run each:** +734 MiB of pin in ASTRO BOT, +194 MiB in the
second title's cutscene arm (lazy names there: orbis_user_malloc, Wwise, SoundAlloc, FileSystem, UIStringAlloc).
ASTRO BOT has the room (8.0 of 13 GiB). The second title does not: its wall is the open problem of this experiment,
and this arm ran with 749 MiB available at the lowest and started to swap. Not measured: the walk route, a long
play, his save at the wall. On these numbers the general rule is affordable for ASTRO BOT and is 0.2 GiB more
against the wall in the second title; import on demand (K1 at the filter: 2 MiB in ASTRO BOT, 0 in the second
title) costs nothing but covers only what packets name.

**Whose the operands "under no view" are [M + code].** In all arms of both titles they are ONE page per run:
0x7f3772b03000, 0x7fcec19b6000 (ASTRO BOT), 0x7ff8c8680000 (second title). `/proc/<emulator>/maps` during the run:
an anonymous private `rw-p` mapping of exactly 12 KiB at that address, far above the guest's range (the unit's
`kGuestMax` is 0xfbffffffff). So it is the HOST's memory, not the title's direct memory and not an alias: one
RELEASE_MEM and one WAIT_REG_MEM64 a frame name it (in ASTRO BOT with `LAZY_BY_DATA`: 6,491 and 6,491 in 112 s).
The filter drops both and the soft CP serves both on the CPU, as designed for memory the GPU cannot see. Not
identified: which host code allocates those 12 KiB and hands the address to the title (an HLE library's own label
or work area [I]). The 0x9f operand 0x408 lies in no mapping at all: it is LOAD_CONTEXT_REG_INDEX's index form,
an offset, not an address (4-10 a run, second title only) [I: from the value; the packet not decoded]. No import can
or should cure these; whether a label in host memory is right against the console is a question for the library
that allocates it, registered in FAULTS.md as an open item, not a fault.

Not done: his play with any of this; the walk route with K1r; a GPU read of written lazy memory (none seen, so
kl412's fault-by-name has not fired); the defaults (K1R off).

### 73. Whose the 12 KiB host page is; the test shortcut prepared; the fold proposed for candidate C (2026-11-13, laptop)

**The host page of section 72 is the VideoOut buffer labels [I, from the code; the address itself not printed].**
The unit's only anonymous mapping of the host is `g_labels` in namespace `Bc5Gc`: `uint64_t[64]` on one page from
`::mmap(nullptr, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)`, the target of
`sceVideoOutGetBufferLabelAddress` (the comment there: experiment 0071 put it on a page of its own "so that it can
be mapped for the GPU"). It fits what was measured: the operand is always the first 8 bytes of the mapping (buffer
0's label), the mapping is anonymous `rw-p` at a host address, and the title names it once in a RELEASE_MEM and once
in a WAIT_REG_MEM64 every frame (write the flip label at the end of the frame's pipeline, wait for it). The kernel
shows 12 KiB because neighbouring anonymous mappings merge. The address is above the unit's `kGuestMax`
(0xfbffffffff), so the anonymous sync never maps it and the filter drops both packets; the soft CP writes and waits
on the CPU. On the console that label is memory the GPU writes. What follows for the picture or the timing is not
measured; what would settle "is it mapped for the GPU at any time": one journal line with `g_labels`' address and a
watch on it (BC5_GUARD_WATCH takes only addresses under views today).

**The maintainer's test shortcut, prepared, NOT installed** (the top's order; his word comes first):
`play-guard-0412.sh` gets the arm `k1rcut` and `shortcut0412b.sh` the entry `k1rcut`, "BC5 emulator (0412 K1R
cutscena)". The arm is fast9's words on g412zd (`BC5_EMU=bin-d`, pinned by `built-d.md5`) plus `BC5_GUARD_K1R=1
BC5_GUARD_K1_FILTER=1 BC5_FAULT_RECORD=1 BC5_DIRECT_TIMEOUT_PROBE=1`, and without e11's reset-replay words
(`BC5_DIRECT_RESET_REPLAY_ACB`, `_RESET_LABELS`, `_RESET_LABEL_JOURNAL`) and the dead `BC5_DIRECT_LEARN_GUEST_ONLY`:
80 words. Checked on the laptop with a stand-in directory (the words, the refusal on a wrong bin-d); not run on the
box. The box's copy of the wrapper must read eb4feddc before this one (d15bcca6) replaces it. RT is the launcher's
setting, as in fast9. `BC5_DIRECT_TIMEOUT_PROBE=1` copies every buffer: its cost in his play is not measured (my
scripted arms ran at 30 flips/s with it).

**The fold into candidate C (exp 0419), proposed to the integrator:** form 1 = g412zd as measured (unit 393a0cbf,
backend 2497a4ce/1d88a8b3); form 2, recommended for a shared build, the same without the read probe pr412 (a
deliberate-fault tool): unit 2f4a3d63, backend direct.hpp 26519fcc, direct.cpp b1d27875, NOT compiled. All switches
default off; the backend archive is a separate swap step that needs the maintainer's word. Not measured: "all
switches off = B" on the box.

The branch was not pushed: this session's permission classifier refused `git push`; the commits are on the local
branch `exp/0412-memory-guardian`.

### 74. The maintainer's test shortcut installed; candidates D and E checked against the chain (2026-11-13 17:16, box; laptop)

His word, relayed by the top, to "Czy zamienic skrot fast9 na skrot testowy z K1r, zebys sprawdzil przerywnik z
ostatniego zapisu?": "Tak, zamien". Installed with `install0412k.sh` (kit `~/bc5-work/exp0412/kit-sc`):
"BC5 emulator (0412 K1r test)" (.desktop 0bd386b5; `BC5_0412_LEAN=1 ... play-guard-0412.sh k1rcut`), the old "BC5
emulator (0412 fast9 bez Plasmy)" moved to `~/bc5-work/trash-20261113/pulpit`. Wrapper b1080e6f (the old eb4feddc
kept beside it), launcher `play-pkg-0412-nolearn.sh` 6a0ae47b (his live saves, `ulimit -c 0`), binary g412zd be507cd5,
RT on in `input.cfg`, fuse 13,000/2,048. The arm `k1rcut`, 77 words: e11 unpacked's 70 without the three reset-replay
words, `BC5_DIRECT_LEARN_GUEST_ONLY`, `BC5_R3_DROP_CATCH`, `BC5_R3_REWIND_CATCH` and `BC5_DIRECT_ACB_INHERIT=journal`
(the top's scope), plus fast9's arm words and `BC5_GUARD_K1R=1 BC5_GUARD_K1_FILTER=1 BC5_FAULT_RECORD=1
BC5_DIRECT_TIMEOUT_PROBE=1`. Checked: the wrapper's dry run on the box. NOT run: this arm itself; the scripted arms
of sections 71-72 had the seven removed words in. His play is its first run.

The integrator's cleanup (exp 0419), laptop only, nothing compiled: on candidate D's unit 2c43382d every anchor of
the chain matches once (full form ends at 4a1bdf0a, form 2 at 92cb76ff). It takes FORM 2 (no probe) for candidate
E; E's unit c92f5913 holds the three rule bodies of k1r0412.inc, cover0412.inc and kl0412.inc verbatim, and differs
inside my functions only in the K1r refusal (the zero-skip half is gone with the option). `memfast/mk0412ze.sh`
builds form 2 on B privately (unit 2f4a3d63, backend 26519fcc/b1d27875, bin-e); not run yet: after his play.

### 75. His play on the K1r test shortcut: no fault; the wall as before (2026-11-13 18:00-18:06, read at 18:10)

His word after the play, relayed by the top: "Wszystko ok. Masz swoje pomiary". Read only (sampler
`~/bc5-work/exp0412/sampler/play-20261113-18{0030,0404}-k1rcut.txt`, journals
`~/bc5-data/captures/play-20261113-18{00,04}/gc/direct.log`, `play-last.log`, `fuse.log`, dmesg), all [M]:

- Two plays on g412zd, arm k1rcut (its first runs): about 122 s and 138 s of frames; the second ended "exit 0". No
  kernel amdgpu line, no new fault record, no "would learn" line, no timeout line.
- K1r: 413-425 covers over 822-846 MiB. kl412: 105-106 written chunks under lazy views without a cover; the named
  fault for a GPU read there did not fire. K1 at the filter: 0 imports.
- Second play: 30.0 flips/s over 134 s, 39 s with a gap over 100 ms, longest 660 ms. No control play without
  `BC5_DIRECT_TIMEOUT_PROBE`, so its cost in a play is still not measured.
- Memory, second play: GTT 12,046-12,067 MiB from 73 s, available 658-739 MiB, swap used 1.6-1.7 GiB, the cgroup's
  peak 12,884 MiB of the fuse's 13,000. The wall is where it was: K1r pins nothing and frees nothing.
- Not established from the files: that the slot-4 cutscene itself played (the journal names no slot or scene). What
  stands: his word, and no fault where the morning's play faulted at once.

### 76. After his play: the defaults turned on and the options removed, for candidate E (2026-11-13 evening, laptop; not compiled)

His words, relayed by the top: "Przerywnik poszedl dalej. Byl plynny. [...] Nic nie zacinalo. Rob dalej testy.
Pozbadz sie zbednych przelacznikow". The top's order for candidate E: K1R + cv412 + kl412 ON by default with no
option that restores the old behaviour; K1 at the filter one rule for both titles; variant (b) off, undecided.

Done in the sources (the .inc files, so the CPU tests test what the unit holds):
- `k1r0412.inc`: `BC5_GUARD_K1R` on unless "0".
- `cover0412.inc`: `BC5_GUARD_K1R_COVERS_VISIBLE` removed; a read-only shared mapping is always a hole for the host
  (the three-argument forms stay as the test's model of the state that faulted).
- `kl0412.inc`, `mkkl0412.py`: `BC5_GUARD_K1R_COVER_WRITTEN` and `BC5_GUARD_K1R_WRITTEN_SCAN_MS` removed; the period
  is the constant 100 ms.
- `mkk1f0412.py`: `BC5_GUARD_K1_FILTER` on unless "0"; "log" names and imports nothing.
CPU tests on the laptop: k1r0412 17,742, cover0412 640,008, kl0412 99,003. The chain on B's unit 8126c0aa (no
probe): mkk1r 1a0ba9aa, mkwa 7aecbf99, mkcv 3c620459, mkk1f ab349ecb, mkkl **2824caf7** (44 lines from form 2's
2f4a3d63); backend unchanged (26519fcc, b1d27875). `memfast/mk0412ze.sh` and `kit-ze.sha256` build it (bin-e).
`mk0412zd.sh` no longer reproduces g412zd from this state of the scripts: g412zd's sources are commit 2ed121cb.

What is left of this experiment's words in that unit:

| word | state | why |
|---|---|---|
| `BC5_GUARD_K1R` | on; "0" off | the one off switch, for the control arm "all off = B" and for telling a K1r defect apart; remove when row 1 is closed on a shared build |
| `BC5_GUARD_K1_FILTER` | on; "0" off, "log" | 2 MiB in ASTRO BOT, 0 in the second title; "log" is the catcher that names what the filter drops |
| `BC5_GUARD_K1R_REPLACE` | off | the map-over form; ran once (k1rg), never shown faster: DELETE candidate, with `map_shared_over` in the backend |
| `BC5_GUARD_LAZY_BY_DATA` | off, UNDECIDED | missing: a GPU read of written lazy memory (kl412's named fault is the proof and has not fired in four arms and his two plays); its price is +734 MiB (ASTRO BOT) and +194 MiB (second title), one run each |
| `BC5_GUARD_WATCH` | off, diagnostic | the state of up to four addresses in the journal; found kl412's defect |
| `BC5_GUARD_K1_STAT` | off, diagnostic | bind statistics |
| removed | | `BC5_GUARD_K1R_COVERS_VISIBLE`, `_COVER_WRITTEN`, `_WRITTEN_SCAN_MS`, `BC5_GUARD_K1R_PROBE` (form 2) |

Not done: nothing of this is compiled or run; the maintainer's shortcut still runs g412zd (be507cd5) with its
explicit words.

### 77. Form 4 for candidate E: the replace form removed; the wall's first measurement joins E's walk arm (2026-11-13 evening, laptop; not compiled)

The top: "K1R_REPLACE: usun, jesli nic go nie czyta poza testem". Nothing read it but run k1rg (section 68), where
it was never shown faster. Removed from `mkk1r0412.py`: the switch, `k1r412_replace_on`, the kept-covers list, the
drop pass's exception, and in the backend `Device::map_shared_over`; `k1r412_map` is now one line (a cover read-only,
anything else as before). `mkcv0412.py` and `mkpr0412.py` follow (their marker of the k1r backend is the tag now).
The chain on B's unit 8126c0aa: mkk1r 496a339c, mkwa 3e5a6851, mkcv 3732021b, mkk1f dcb7aa43, mkkl **9a54eaa4**
(48 lines from form 3's 2824caf7); backend direct.hpp e96e5c73, direct.cpp 28100ce5. `mk0412ze.sh` and
`kit-ze.sha256` follow. Section 76's table loses the `BC5_GUARD_K1R_REPLACE` row. Not compiled: this form changes
the backend, so it gets a private build and the two arms before E goes anywhere.

The wall's first measurement (PLAN-memory-wall.md, step 1) rides on E's walk arm, by the top's order, with these
words: `BC5_DIRECT_ZEROSCAN_AT=<five times after gameplay starts>` and `BC5_DIRECT_ZERO_NAMES=<the launcher's
BC5_DIRECT_EAGER_NAMES list>` (the scan reads only eager views of the named heaps and journals, per heap and scan,
"zero now" and "zero in all N scans": the last line per heap is B's floor on that route), plus one `snap0412.sh`
with the emulator's `fdinfo` near the end for the 555 MiB of host buffers. Log only; no skip, no list is used. No
arm with a GPU write risk is prepared: that waits for the number and for his word.

Candidate E as the integrator made it (exp 0419, 2026-11-13 evening): from FORM 3, not form 4 (the messages crossed):
my unit 2824caf7 plus its four generators gives unit 1215d7d7, patch 2dd4c95c; backend 26519fcc / b1d27875; the
replace form stays in E until the next backend change. E's sources of my chain are commit 173a38b4. Checked on the
laptop: the three rule bodies are in 1215d7d7 verbatim. In E the read of `BC5_DIRECT_ZERO_NAMES` is a constant, so
the log-only zero scan sees its two default heaps (RenderGpuWcLarge, CommitIABufferAllocator) unless the read is
given back (asked). Order agreed: the integrator builds E privately and runs its chain; then my two arms on that
binary (ASTRO BOT 120 s; the cutscene arm to its end).

Later the same evening the integrator regenerated E from FORM 4: unit 9a54eaa4 -> 449878ca, patch 410273ca, private
backend e96e5c73 / 28100ce5, the read of `BC5_DIRECT_ZERO_NAMES` given back. Checked on the laptop: the three rule
bodies verbatim, no replace form. E's sources of my chain are commit 0e2c7e56. After its chain I run three arms on
its binary: ASTRO BOT 120 s, the cutscene arm to its end, the walk with the zero scan.

### 78. E's private chain read: K1r's cover pass costs 20 ms a rebuild and stalls the menu for a second; the wall's first numbers (2026-11-13 19:14, reads only)

The integrator (exp 0419) built candidate E from form 4 privately (binary 93188758, backend archive d4c4882e) and
ran its chain with my arms inside; its report: ASTRO BOT 120 s PASS; the cutscene arm k2cut to G+320 with no fault
and no record (K1r 406 covers / 808 MiB, kl412 110 chunks); the walk k4wall to G+560 clean. It flagged the longest
frame gaps: 1,238 ms (k1, defaults) and 1,357 ms (k2cut) against 638 ms with `BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0`
(k1off). Read on the top's GO (one lock line, greps only; the small results in `raw/readE/`).

**The gaps [M]** (frame-profile lines over 500 ms; journals `play-20261113-1838` k1, `-1845` k1off, `-1851` k2cut,
`-1901` k4wall):

| run | t s | gap ms | where the frame profile puts it |
|---|---|---|---|
| k2cut | 39.6 | 1,357 | at the flip 1,287 |
| k4wall | 39.4 | 1,076 | sync 1,029 (game thread) |
| k1 | 249.2 | 1,238 | outside the host 1,122; sync 47, GPU 31 |
| k1off | 99.2 | 638 | outside 427, at the flip 179 (the load; every run has it) |

Both 39 s gaps are in the menu, 75 s before gameplay. The timing split's "want" step of the mapping rebuild:
18.8-20.3 ms per full sync with K1r on (k4wall), 0.8 ms with it off (k1off) [M].

**The cause [I, from the code]:** `k1r412::cover()` walked the list of imported buffers from its start for every
view; with 21,000 views that is millions of steps a rebuild. Around 39 s the title maps its views and every change
is a full rebuild, so the 20 ms add up to a second (in k2cut the game thread waits at the flip for the rebuild on
another thread [I]). The 1.1 s "outside" of k1 at 249 s is not attributed: not sync, not GPU, one run. The 39 s
stall is in 2 of 3 K1r-on runs here and in 0 of 1 off; my arms on g412zc/zd and his play had 356-722 ms at most.

**The fix, form 5 (laptop, CPU test 17,742 of 17,742; not compiled):** `cover()` starts at the last buffer that
begins at or before the view (binary search; the list is sorted and disjoint). Chain on B's unit: mkk1r ad75c63f,
mkwa 416f7a93, mkcv 9a467d3c, mkk1f a0ee1521, mkkl **46219eed** (8 lines from form 4); backend as form 4 (e96e5c73,
28100ce5). The pass mark on the box: "want" under 2 ms per full sync with K1r on, and k1 / k1off / k2cut twice each.
**E is not ready for the swap until then; row 1 of FAULTS.md closes on the fixed E.**

**The wall, first numbers [M]** (k4wall: the log-only zero scan at t 175, 295, 415, 535, 640 s over the 18 eager
heaps, 17.0 GiB of spans; frame numbers of this arm are not comparable):

| heap | span MiB | all-zero in every one of the 5 scans, MiB |
|---|---|---|
| RenderGpuWcLarge | 2,758 | 842 |
| CommitIABufferAllocator | 2,736 | 274 |
| RenderGpuRwLarge | 414 | 204 |
| DynamicHeap (+ Small) | 328 (+54) | 160 (+22) |
| AMM | 10,084 | 154 |
| Physics | 192 | 116 |
| ComponentHeap (+ Small) | 104 (+36) | 56 (+24) |
| the other nine | | under 20 each |
| **all** | 17,001 | **1,930** (per scan 2,118 / 2,002 / 2,058 / 2,044 / 1,966) |

Option B's floor on this route is about 1.9 GiB of pinned 2 MiB chunks nobody wrote in ten minutes: over the plan's
500 MiB gate. (The spans are reservations: the heaps' pinned size is smaller for AMM.)

GTT at 615 s, 12,220 MiB, by client (`k4wall-snap.txt`, `k4wall-fdinfo.txt`) [M]: the emulator's direct client
11,822; the emulator's second client (its Vulkan/present side) 245 GTT + 236 VRAM; plasma-keyboard 76; Xwayland 22;
plasmashell 20. Available 657 MiB. For his play's 555 MiB beyond the guest this gives about 245 present side, about
100 desktop clients, about 210 the direct path's own buffers [I: the split is k4wall's, the 555 is his play's].
plasma-keyboard's 76 MiB can go in the lean session.

### 79. For candidate F: the cover pass's cost in a CPU test; the catcher for unnamed writers; the heaps' order (2026-11-13 evening, laptop; not compiled)

The top's order: form 5 goes into candidate F (E + form 5 + exp 0418's diff) with a CPU test that shows the old
cover pass's cost; step 2 of the wall plan enters F as a diagnostic, off; the heaps' order and each arm's risk are
written down; plasma-keyboard joins the lean list on paper.

- **The cost test** (`k1r0412.cpp`, now 17,745 checks): 21,000 views over 600 imported buffers. The pass before
  form 5, kept in the test as the reference, looks at 6,201,535 list entries; `k1r412::cover()` with the binary
  search at 27,072; the pieces are identical. `cover()` got an optional step counter for this.
- **ww412** (`BC5_GUARD_WRITERS=1`, default off, log only): `ww0412.inc`, `ww0412.cpp` 105,737 of 105,737,
  `mkww0412.py`. Hooks: `direct_force` names every chunk a hint or force asks for; `ww412_packets` names the chunks
  of every memory operand of a submission's main buffer; the zero scan's thread compares each heap's flags with the
  last scan's and journals "turned non-zero: N named, M NOT named". Limits in the file's header.
- **Form 6** on B's unit 8126c0aa: mkk1r dffb4216, mkwa 46f2cf87, mkcv 2d466d15, mkk1f 6944eaf8, mkkl 1a2535ee,
  mkww **b76dc93e**; backend as form 4 (e96e5c73, 28100ce5). `mk0412ze.sh`, `kit-ze.sha256` follow.
- `PLAN-memory-wall.md` has the first measurement's result, step 2, the order of the heaps with each arm's risk
  (no arm prepared), and the lean list's new line.

### 80. Candidate F's acceptance chain, read for the cover pass's cost (2026-11-13 19:32-20:21; the integrator's runs and readings, exp 0419; nothing run by this experiment)

F: patch d9af28ca, unit 59d17cf5 (form 6 of section 79; the four rule bodies are in it verbatim, checked on the
laptop). Arms: m1a, m1b (walk, K1r on), m1offa, m1offb (`BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0`), m2cuta, m2cutb
(cutscene to G+320, K1r on), ASTRO BOT 120 s three times, lean. Kernel errors 0, crashes 0, no fault record in all.
Raw files on the box, not copied: `~/bc5-work/exp0413/n/raw/fchain.out`, `m*-journal.txt`.

"want" per full sync = the timing-split line's "want" (a total in ms over 128 submissions, read in the unit)
divided by its count of full syncs [M, the integrator's `want0419.sh` over every line with a full sync]:

| arm | K1r | lines with a full sync | over 2 ms | largest three, ms (at t, s) |
|---|---|---|---|---|
| m1a | on | 1905 | 64 | 3.10 (63.4), 3.00 (52.0), 2.90 (65.9) |
| m1b | on | 1955 | 103 | 3.30 (51.0), 3.20 (56.0), 3.15 (49.2) |
| m2cuta | on | 2612 | 29 | 3.10 (50.6), 3.10 (46.1), 3.00 (51.1) |
| m2cutb | on | 2444 | 48 | 2.90 (67.7), 2.80 (46.2), 2.75 (45.3) |
| m1offa | off | 1911 | 0 | 1.50 (335.7), 1.20, 1.10 |
| m1offb | off | 2013 | 0 | 1.40 (88.5), 1.20, 1.20 |

Candidate E (the pass before the binary search): 18.8-20.3 ms. Longest gaps: K1r on 698, 695, 408, 678 ms, off
879, 625 ms, all at 92-155 s (the load and after); none near 39 s, where E stalled for about 1 s.

- The mark as I wrote it ("want under 2 ms per full sync with K1r on") is **not met** at the maxima: about 3 ms
  at worst, all between 45 and 68 s (the menu), in 1-5 % of the windows. K1r adds at most about 1.6 ms to a full
  sync there [M].
- What the mark stood for, the stall, is **gone** [M]: no gap came with those windows, and K1r on and off have
  the same longest gaps and the same flips/s (25.4-25.7 walk, 29.5-29.8 cutscene).
- My verdict: **F is ready for the swap** from this experiment's side. The 2 ms was my guess at a safe number,
  not a measured limit; 3 ms in a full sync is under a tenth of a frame at 30 flips/s.
- Not known: where the remaining 1.6 ms goes (the cover pass itself, or kl412's data scan). A form 7 is not
  prepared; it would start from a split of `k1r412_want`'s time, as a diagnostic.
- FAULTS.md row 1 closes on m2cuta and m2cutb: the cutscene ran to G+320 twice on the fixed build with no fault.

### 81. The long walk on F with the zero scan and the writers catcher (arm m5wall): a GPU hang at 601 s; ww412's first numbers (2026-11-13 20:22-20:33, the integrator's run; read here 20:55-20:57, read only)

Arm m5wall: F's private binary, walk to G+560, `BC5_DIRECT_ZEROSCAN_AT=175,295,415,535,640`,
`BC5_GUARD_WRITERS=1`. **A GPU hang at 601 s**: the kernel's "ring gfx_0.0.0 timeout", reset succeeded, no
reboot; the fault record ended the game (605 s). Record: `~/bc5-data/captures/faults/20261113-203301`; journal
`~/bc5-data/captures/play-20261113-2022/gc/direct.log` (on the box; not copied: they hold the title's buffers).
Section 80's verdict "F is ready for the swap" is **withdrawn** until this is explained or shown not to repeat.

What the record says [M]:
- No page fault (fault address 0, status 0). Two jobs timed out after 2 s: acb #522931 (816 dwords: 0 waits,
  10 label writes, 20 dispatches, 18 of them indirect) and dcb #522934 (45,179 dwords: 32 waits, 30 kept for the
  GPU, 421 label writes, 34 dispatches).
- The frames up to 599.0 s are ordinary (33 ms a flip, GPU busy 25-32 ms). Memory at 600 s: available 406 MiB,
  swap 665 MiB, GTT 12,331 of 13,312.
- The probe finds nine waits "NOT met" in the dcb. All their labels (0x11e0270460 ... 0x11e0bd0950) lie in one
  ordinary mapping, 0x11e0000000 + 0xe14000, of the eager heap RenderGpuRwLarge. An eager heap gets no K1r cover.
  The probe reads the labels after the reset, when the memory was reused: "NOT met" there proves nothing.
- K1r's last line before the hang (229 s): 378 zero pieces over 752 MiB; the zero buffer holds 0 non-zero words.

Can ww412 or K1r be in it? [I]
- ww412: by mechanism no. It reads packets and fills a set under its own mutex on the CPU; it changes no
  mapping, no packet, no label. It adds CPU time to each submission (not measured).
- K1r: no sign of it, and not excluded. Its two known failure kinds do not fit as seen: a GPU write into a cover
  is a page fault (there is none); a wait on a label under a cover would hang without a fault, but the labels
  found are not under a cover. What stays possible: a shader that reads zeros where the console has data and
  does not finish. One run cannot tell.
- What differs from E's clean walk of the same length (k4wall): form 6 for form 4, ww412 on, exp 0418's
  start-state table. E ran at GTT 12,220 at 615 s; this run at 12,331 at 600 s.
- The arms that tell them apart, in this order: the same walk on F with no scan and no catcher; if it hangs,
  again with `BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0`; if it still hangs, with exp 0418's rows off. The
  integrator proposed the first; all are scripted, on a private save copy, with the fault record on.

ww412's first numbers [M]: chunks (2 MiB) that turned non-zero between two scans, and how many of them no hint,
force or packet operand had named (scans at 175, 295, 415, 535 s; the fifth never ran):

| heap | turned, scans 2 / 3 / 4 | NOT named | of all turned |
|---|---|---|---|
| RenderGpuWcLarge | 45 / 35 / 27 | 4 / 5 / 2 | 11 of 107 |
| RenderGpuRwLarge | 22 / 6 / 1 | 16 / 6 / 1 | 23 of 29 |
| CommitIABufferAllocator | 10 / 7 / 1 | 9 / 1 / 1 | 11 of 18 |
| AMM | (span changed) / 28 / 9 | 0 / 0 | 0 of 37 |
| the other thirteen heaps | 0 | 0 | 0 |

- CommitIABufferAllocator is **not shown clean**: 11 chunks got data that nothing named. For this heap the CPU
  is the expected writer, and a CPU write is seen by the data scan; the catcher cannot tell a CPU write from a
  GPU write. The order of PLAN-memory-wall.md stands, with that limit.
- RenderGpuWcLarge: 90 % of what turned was named. The 11 not named are the open risk of its arm.
- RenderGpuRwLarge: mostly not named (23 of 29). It should go last of the three, or get a naming rule first.
- AMM: everything that turned was named (37 of 37 in two intervals). That contradicts my "every catcher is
  blind there"; the plan's row is corrected to "leave eager until the hang is understood".

A by-product, the cost of kl412's data scan [M]: 0.48-0.51 ms a scan (750 scans, 103,798 SEEK_DATA calls,
384 ms by 229 s). That is about a third of the 1.6 ms K1r adds to a full sync (section 80).

### 82. Prepared for option B's arms: one switch per heap (bd412) and the CPU/GPU split of the writers catcher (wc412) (2026-11-13 late evening, laptop; not compiled on the box, not run)

The maintainer's word, relayed by the top ("jest moja zgoda"): scripted arms of option B, heap by heap, on a
PRIVATE build and a private save copy, with a possible GPU fault or reboot. Not covered: shared builds,
launchers, shortcuts, his live saves, runs while he plays. The top's conditions: the hang of section 81 is
explained first; all heaps' rule in one build, one switch per heap, with a catcher that tells CPU from GPU
writers if that can be done; one arm = one heap, CommitIABufferAllocator first, fault record on, stop and report
after a reboot; each arm reports the MiB recovered at m5wall's points, flips/s and the longest gap.

- **bd412, `BC5_GUARD_BYDATA_NAMES=name[,name...]`** (default unset: nothing changes). A heap named there is
  not imported whole though `BC5_DIRECT_EAGER_NAMES` names it: `direct_eager_name` answers no for it, so it is
  imported where the file holds data and where a hint, a force or a packet operand names a chunk; K1r covers
  the rest. The zero scan and the catcher keep reading it (they asked for eager views only). `bd0412.inc`,
  `bd0412.cpp` 27,008 of 27,008.
- **wc412, `BC5_GUARD_WRITERS=2`** (=1 stays ww412 with its lines unchanged). Linux's soft-dirty bit
  (/proc/self/pagemap bit 55, cleared by "4" into /proc/self/clear_refs; the kernel's
  Documentation/admin-guide/mm/soft-dirty.rst) is set by a write through the process's page tables and not by a
  write of the GPU. Per scan: the bits of every slot that was zero at the last scan, the clear, the scan, the
  bits again for the slots that turned; a not-named chunk is then "written by the CPU" or "NO CPU write: a GPU
  writer nobody named" (up to 64 of those are journaled by offset). The first scan tests the bit on a page of
  its own and says so if it does not work on this kernel. `wc0412.inc`, `wc0412.cpp` 6,010 of 6,010.
  Costs, not measured: the clear write-protects every page of the process, so an arm with =2 is a diagnostic
  arm of its own; its gaps and flips/s do not compare with other arms.
  TODO(verify): that this kernel is built with CONFIG_MEM_SOFT_DIRTY, and that the bit is kept for the shared
  mappings of the direct file; the self-test answers the first, the first run's numbers the second (a heap
  whose turned chunks are ALL "no CPU write", CommitIABufferAllocator above all, would mean the bit is not
  kept there).
- `mkbd0412.py` applies to a unit with ww412: candidate F's 59d17cf5 gives **8f07ccf6**, form 6 (b76dc93e)
  gives 2dc64fc8. The glue passes a syntax check on the laptop against stand-in declarations (clang++
  -fsyntax-only -Wall -Wextra -Werror); it has not been compiled on the box.
- The box build script is NOT written: its base (F as it is, or F with exp 0418's rows off) follows from the
  integrator's series on the hang.

The arms, when the slot comes (each: F + bd412/wc412 private build, walk to G+560, RT on, fuse and watchdog,
fault record on, private save copy; GTT and available memory read at 420 s and 600 s, where m5wall had 12,237
and 12,331 MiB of GTT and 409 and 406 MiB available):

| arm | switches | risk | answers |
|---|---|---|---|
| w0 | `BC5_GUARD_WRITERS=2`, zero scan as m5wall | none beyond a walk (a diagnostic; slower) | per heap: how many not-named chunks the CPU wrote, how many it did not |
| b1 | `BC5_GUARD_BYDATA_NAMES=CommitIABufferAllocator` | GPU fault or reboot | the rule on a real heap; MiB recovered (floor 274) |
| b2 | `...=RenderGpuWcLarge` | the same, higher | floor 842 |
| b3 | `...=RenderGpuRwLarge` | the same, highest by ww412's count | floor 204 |
| b4 | `...=DynamicHeap,ComponentHeap,Physics` one at a time | the same | floors 182, 80, 116 |

An arm is run only after the one before it is read; a fault's record names the writer, and that writer's
class gets an import rule before the heap is tried again.

### 83. The series for F's hang, read for K1r; the cover pass old against new on generated layouts (2026-11-13 21:00-22:00 the integrator's five walks to G+620, exp 0419 README section 14; read here 22:1x, read only)

| arm | build and switches | result [M, the integrator] |
|---|---|---|
| sA | F plain (K1r on) | **the title faulted on the CPU at 543 s**: read of 0x17fc at eboot+0x1b349f; no GPU fault, kernel lines 0 |
| sB | F, `BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0` | clean, 26.3 flips/s, longest gap 739 ms |
| sC | F without exp 0418's five new rows (K1r on) | clean, 25.9, 1,020 ms |
| sD | shared B | clean, 26.1, 875 ms |
| sE | F + zero scan + `BC5_GUARD_WRITERS=1` (m5wall again) | clean, 24.8, 573 ms |

Long walks past G+320 so far: F with K1r on 2 failed of 4 (the GPU hang of section 81; this CPU fault), F with
K1r off 0 of 1, E (form 4) 0 of 1, B 0 of 1.

**What precedes the CPU fault in sA** (journal `~/bc5-data/captures/play-20261113-2100/gc/direct.log`,
`~/bc5-work/exp0413/n/raw/sA-crash.txt`; on the box):
- [M] The instruction is `movzx ebx, word [r11+r10-4]` in a loop that copies 16-bit words (rax = r8 = rdx =
  0x200; the bytes before it compute r10 = 2*r10 + [rdi]). r10 is 0x1000 and r11 0x800: the base pointer read
  from the title's own structure at 0x131c7bf580 was 0. A READ by the title's CPU through a null base.
- [M] No K1r event before it: the k1r line is written when the number of covers changes (at most every 10 s);
  its last line is at 152 s (380 pieces, 756 MiB), so the cover count did not change for 390 s. K1 at the
  filter imported nothing in the whole run (0 lines, as in all five runs). No GPU fault, no "would learn", no
  failed submission. Memory at 530 s: available 531 MiB, GTT 12,271.
- [M] The lines of the last seconds are the ordinary ones (merges, "flip label still set", one
  "cpu-wait WAIT_REG_MEM64 ... GIVEN UP after 16.3 ms"); the run has 96 of those, sB 99, sC 168, sD 44, sE 147.
- [I] A CPU read cannot see a cover. sB ran the same route with K1r off and had no GPU fault, so on that run no
  GPU read reached memory a cover would have hidden; that speaks against "zeros read through a cover" as the
  source here. Why the title's pointer was null is NOT known.

**Form 6 (F) against form 4 (E)**: form 5 changed one thing, the start of `k1r412::cover()`'s walk (a binary
search for the last buffer that begins at or before the view's start); form 6 added ww412, which does nothing
unless `BC5_GUARD_WRITERS` is set. F also carries exp 0417's save fix and exp 0418's diff, which E did not.
- [M, the code] The search relies on the buffer list being sorted and disjoint. It is: the only insert into
  `S.bos` goes through `std::upper_bound` on the offset, and the merge replaces a run by one buffer in place.
- [M, laptop] `k1r0412.cpp`, now 209,746 of 209,746: on 4,000 generated layouts (0-12 buffers, adjacent or
  with gaps) and 96,000 views placed on buffer edges, one page before and after them, inside and across
  buffers, the two passes give the same pieces in every case (differ in 0); each view is also checked page by
  page against a model (a page is covered exactly when no buffer holds it). I find no defect in form 5's pass.

**The shortest series that decides** (scripted, long walks to G+620, no build needed): the kept F binary twice
plain and twice without exp 0418's rows; E's kept private binary (form 4) twice if it still exists (only B and F
are in `exp0413/kept`). Six walks, about 70 minutes. F plain fails again and "without rows" does not: exp 0418's
rows. Both fail and E does not: forms 5/6 or exp 0417's fix. Nothing fails: the rate is under about one in
four and only more walks tell.

**ww412 from sE, all five scans** [M] (not named / turned non-zero, 175-640 s): RenderGpuWcLarge 11 of 98,
RenderGpuRwLarge 30 of 35, CommitIABufferAllocator 10 of 20, AMM 1 of 60, VisualEffectInstanceHeap 1 of 1, the
rest 0. As in section 81. Zero in all five scans: RenderGpuWcLarge 902 MiB, CommitIABufferAllocator 280,
RenderGpuRwLarge 192, DynamicHeap 160 + 22, Physics 116, ComponentHeap 56 + 24; all listed heaps 1,828 MiB.

Not updated: `kit-ze.sha256` (it names the old `k1r0412.cpp`; that kit was never sent).

### 84. The deciding series was run by the integrator: nine long walks, none failed (2026-11-13 22:06 - 2026-11-14 00:01; exp 0419 README section 15, 71d552d7; not read on the box by me)

[M, the integrator] Nine walks to G+620, interleaved: F plain x3, shared B x2, F with `BC5_GUARD_K1R=0
BC5_GUARD_K1_FILTER=0` x2, F without exp 0418's five new rows x2; `KYTY_BC5_MEM_FIRSTFAIL=1 KYTY_BC5_TRAP_LOG=1`
in all. All nine reached G+620 with 25.1-25.6 flips/s, 0 kernel lines, 0 crash lines, no new fault record.
Lowest available memory in 580-620 s: 389 MiB; GTT 12,177-12,323 of 13,312. Raw:
`~/bc5-work/exp0413/n/raw/counts0419f.out`, journals `~/bc5-data/captures/play-20261113-2206` to `-2349`.

Long walks past G+320 now: F with K1r on 2 failed of 7 (the GPU hang at 601 s, the CPU fault at 543 s), F with
K1r off 0 of 3, F without exp 0418's rows 0 of 3, B 0 of 3 (E's form-4 binary was not run).
- [M, arithmetic] 2 of 7 against 0 of 3 (K1r off alone): p 0.47 (21 of 45). 2 of 7 against 0 of 9 (all other
  arms together): p 0.175 (21 of 120). Neither separates.
- [I] This is section 83's third outcome: nothing failed, so no arm is named. The two failures are of two kinds
  (a GPU ring timeout without a page fault; a null pointer in the title's own structure), each seen once in 16
  long walks; nothing shows they share a source, and nothing ties either to K1r beyond the arm they fell in.
- NOT known: the source of either. The records of both stay the only evidence (`FAULTS.md`).

What this leaves for option B's arms: the top's first condition ("the hang is explained first") is NOT met and
cannot be met by more reading of these runs. Whether the arms start on F with the two faults open at about 1 in
8 long walks each is the top's and the maintainer's call; an arm that hangs or faults the same way would then
not be attributable to its heap without the fault record saying so.

### 85. The night of 2026-11-14: build g412zf, the first pairs F / w0, and arm b1 (CommitIABufferAllocator by data): a GPU WRITE nobody named, at the load

The top's GO (00:0x): the box until 07:00 for long walks on F with catchers, arm w0, and b1 once after two clean
w0. Its own condition "the hang is explained first" was withdrawn by it; the maintainer's word for the wall's arms
stands ("jest moja zgoda": scripted, private build, private save copy, heap by heap).

**Build g412zf** (`mk0412zf.sh`, kit-zf; private copies only; exp 0413's private tree and backend source read and
checked against its `tree18.md5`): candidate F's unit 59d17cf5 -> `mkbd0412.py` 8f07ccf6 -> `mkkc0412.py unit`
7af3f752; `memory.cpp` f51c803e -> `mkkc0412.py memory` afc69dfe. Binary **f8cb77ad** (`~/bc5-work/exp0412/bin-n`),
17 build steps, no new warning in the two files. CPU tests on the box: bd0412 27,008, wc0412 6,010, kc0412 48,009,
ww0412 105,737, k1r0412 209,746, all of all. New, both default off:
- **kc412, `BC5_GUARD_COVER_LOG=1`**: one journal line for every mapping rebuild in which a K1r cover gave way to
  the title's data (count, MiB, first address, heap). Log only. `kc0412.inc`, `kc0412.cpp`.
- **the arming line of ff412**: `KYTY_BC5_MEM_FIRSTFAIL` says "armed" at the process's start (a static initialiser in
  memory.cpp that asks the catcher's own switch), so "it printed nothing" now means "no wrapped call failed".

**The chain** (`night0412.sh`, runner `run0412p.sh` = exp 0413's run0413p.sh with exp 0412's directory, by
`mkrun0412p.py`): one lock line; every arm a walk to G+620 from the named snapshot's private copy, RT on,
`N_FUSE="13000 2048"`, `N_WD_MIB=220` (the sixteen earlier long walks ran with 12,400/1,024 and 300),
`KYTY_BC5_MEM_FIRSTFAIL=1 KYTY_BC5_TRAP_LOG=1 BC5_GUARD_COVER_LOG=1`, the fault record on, sampler every 5 s, pad
keys recorded (0 in every arm). Kernel 7.2.15-ogc1.1 (CLAUDE.md records 7.2.11: not re-read for Mesa/libdrm here).

| arm | words beyond the catchers | result [M] | flips/s, longest gap | avail / GTT MiB at 420 s; at 600 s; lowest avail |
|---|---|---|---|---|
| n8F1 | none | clean to G+620 | 25.8, 653 ms | 624 / 12,353; 579 / 12,197; 471 |
| n8W1 | w0: `BC5_GUARD_WRITERS=2`, zero scan at 175,295,415,535,640 | clean | 25.8, 638 ms | 716 / 12,252; 570 / 12,312; 459 |
| n8F2 | none | clean | 25.7, 761 ms | 544 / 12,257; 656 / 12,307; 396 |
| n8W2 | w0 | clean | 25.5, 572 ms | 535 / 12,331; 671 / 12,288; 481 |
| n8B1 | b1: `BC5_GUARD_BYDATA_NAMES=CommitIABufferAllocator` | **GPU page fault, a WRITE, at 111 s (in the load, before G)**; ring reset succeeded, no reboot | - | at 108 s: 1,361 / 11,430 |

In all five: the three catchers armed (1 line each), first-failure lines 0, trap lines 0, k1f imports 0 in the F and
W arms.

**w0, what the soft-dirty split says** [M] (it works on this kernel: the self-test passed, the clear takes 49-67 ms
for the whole process, 110-133 ms with the reads; flips/s as in the F arms). Not-named chunks that turned non-zero,
"written by the CPU" / "NO CPU write", scans 2-5:

| heap | n8W1 | n8W2 |
|---|---|---|
| RenderGpuWcLarge | 0 / 13 | 0 / 8 |
| RenderGpuRwLarge | 0 / 16 | 0 / 13 |
| CommitIABufferAllocator | 1 / 0 | 8 / 0 |
| AMM | - | 1 / 0 |
| VisualEffectInstanceHeap | 1 / 0 | - |

- [M] Every not-named chunk of the two RenderGpu heaps is a GPU write nobody named; every one of
  CommitIABufferAllocator, AMM and VisualEffectInstanceHeap had a CPU write.
- [I] So the scans from 175 s on show no unnamed GPU writer in CommitIABufferAllocator, and b1 was started on that.
  The scans do not cover the load (the first is at 175 s, G is at 115 s). That gap is where b1 failed.

**b1** [M] (record `~/bc5-data/captures/faults/20261114-010740`, journal
`~/bc5-data/captures/play-20261114-0105/gc/direct.log`; neither is copied):
- kernel: page faults at 0x121a807000, 0x121a802000, 0x121a801000, client TCP (0x8), RW 1,
  status 0x00741041, PERMISSION_FAULTS 0x4; the host's line: "under the read-only zero cover: a GPU WRITE (kind
  K1w)"; view "CommitIABufferAllocator" 0x1210000000+0xab000000, the address 0xa807000 into it, chunk never written
  by the CPU.
- before it: k1r at 106 s 748 pieces, 1,492 MiB covered (the F arms have 380 pieces, 756 MiB from 152 s on); the
  cover log's last lines at 109.24 and 109.26 s are covers in CommitIABufferAllocator giving way to CPU data, as
  intended; K1 at the filter imported 5 operands (op 0x50, 20 MiB), the F arms 0.
- the job that timed out (#91068, an acb of 84 dwords, dumped by the probe) holds no dispatch: label writes, one
  ACQUIRE_MEM, one compute user-data block. It waited behind the faulting job; the writer is an earlier submission
  and is NOT identified. Its target is not a packet operand, a hint or a force: TCP is the client of a shader's own
  loads and stores, so the address came from a buffer descriptor the shader was given.
- memory: at the fault 1,330 MiB available and GTT 11,464 MiB against about 11,2xx at the same second of the other
  arms is NOT a like-for-like number (the load was not over); "MiB recovered at 420 s and 600 s" was not reached.
- no failed memory call before it (first-failure lines 0, armed).

[I] What it means for the rule: "by data + cover + named write targets" is not safe for CommitIABufferAllocator as
the host names targets today. The class missing is a buffer a shader writes through its descriptor (bound by user
data, not by a packet operand). The next attempt needs that class named BEFORE the write: either the import of
every buffer descriptor a dispatch or draw is given, or a catcher that lists them first (log only) so that the
size of the class is known. b2 and later arms are not started (the top reads this first); the RenderGpu heaps have
unnamed GPU writers in every scan, so they would fail the same way sooner.

The chain went on with F / w0 pairs after b1 (no reboot). Their table follows in section 86.

## Verdict

- **K1r and rl412 (sections 62, 63; not compiled):** the fault of his play gets a read-only zero cover over
  never-written memory the title mapped (nothing pinned; a GPU write there faults by name), and the freeze after
  the reset gets the lost labels kept when two jobs time out together. One private build carries both with the
  catchers.
- **His first play without the learned file (section 62):** one GPU fault at 286 s in a cutscene; the reset succeeded but the title froze (the lost job's label writes were never written: our recovery's defect). The fault: a shader READ of
  a never-written chunk of `AssetHeap Large`. Its right answer was zero: the rule is a read-only zero cover over
  never-written chunks of by-data heaps (E1's measured case), not a window. The lean session worked in real play.
- **No learned windows any more (section 60, the maintainer's order):** his shortcut (fast9, the shared build) and the
  three shared launchers of the second title run with an empty learned file and the catcher that only logs; the
  old file is in the trash directory. A fault is now a bug report with an address and a kind.
- **Compaction (section 58, sources only):** kcompactd is driven by the kernel's own proactive compaction and by every
  kswapd pass once 12 GiB is pinned; our import adds order-5 array requests per 64 MiB buffer on every create,
  merge and cut. The first is a system setting that only the maintainer can change; ours needs buffers made once.
- **The 12,800 MiB offer (section 57):** the recorded deaths at 12,460–12,800 are ours (the AMM auto pool's refused
  borrow), the start deaths at 12,288 and below were never read; all predate exp 0413's set-buffer guard. Measured
  gain at 12,800: 190–220 MiB of GTT, not 1 GiB. A catcher naming the first failing memory call is proposed, not built.
- **Without the learned file on the shared build (section 56):** 15 minutes of scripted play, no fault, nothing the
  catcher would have learned, 25.8 flips/s. The route does not need the file; his own play is not covered by this.
- **E1 (section 55):** on gfx1013 a shader's read of a PRT page and of a read-only page gives zeros with no fault; a
  write to a PRT page vanishes silently; a write to a read-only page is a named page fault that costs the job and
  one recovered ring reset (fence timeout at 2.03 s; a new context checked 15 s later) and leaves the page intact.
  One sample each, no game running. A read-only zero mapping is a detector of GPU writes, not a way to keep
  them; a PRT page is a cover only where the title mapped nothing.
- **The rule's first test (sections 52, 53):** the scripted route needs none of the 81 learned windows (three runs,
  1,022 s, no fault; 246 MiB less pinned). "Pin every view whole" (R1) reaches the memory wall in the menu and is not
  runnable today. The arm with R1 and the PRT background hung the GPU without a page fault and the box rebooted;
  whether the wall or the PRT span did it is open. Build g412x (`bin-x`) holds the three switches, all off.
- **Stopping Plasma's shell for the play is worth 0.22 GiB at the wall (section 50):** lowest available 724 and 775
  MiB without it against 497 and 560 with it; the launcher's lean mode stops it and brought it back in its first
  test. Not in his shortcut yet. `plasma-keyboard` and Xwayland hold 96 MiB of GPU memory more.
- **The learned windows (section 51, `DESIGN-learned-windows.md`):** 81 on file, none learned tonight; 15 lie wholly
  where the guest maps nothing, most of the rest inside heaps imported whole anyway. Their cause is ours: the GPU's
  address space is a guessed subset of the title's. The replacement is a rule in two parts: a PRT background under
  every unmapped address (no memory, already in use for the AMM window) and every mapped range handed to the GPU at
  the title's map call (+768 MiB pinned on the scripted route, so only after options A–C made room). Not built.
- **The architecture stays; the wall is closed from outside the title first (section 49, design only):** others avoid
  the wall by copying and translating, which the direct path cannot do. Proposed order: the console's budget outside
  the title (A), then sound handling of never-written pages (B) behind experiment E1. Nothing measured yet.
- **The zero skip is unsound by design; proposed out of fast7 (section 48) [M]:** every run has GPU writes into
  "skipped" memory, readable through other chunks and then lost. A search before submission (BC5_GUARD_ZSKIP_SCAN, g412w,
  default off) leaves 1 hit per run and ends the skip at 47 s anyway. Without the skip the route's lowest available
  memory is about 300-450 MiB instead of about 890. Waiting for the maintainer's word on his shortcut.

**After the unattended night (section 9): a cgroup memory limit keeps the box alive, and the zero skip with a list scanned at his save removes the memory pressure in scripted runs of his save; the frame rate there is GPU-bound and did not change. Not yet seen or played by him.**
- **The zero skip hangs the GPU without fast7's full word set (section 47) [M]:** 5 hangs in 8 runs without
  BC5_GUARD_LEDGER (his lean7 play, exp 0413's build, three scripted runs) against 0 in 16 with fast7's words.
  lean7 is not for play. Which word protects and why is not shown; the canary's sharing is the suspect [I].
- **The 10 s release hangs the GPU with the zero skip (section 46) [M]:** one hang in one run (fast6), as the old zo arms (3 of 9); with 30 s
  none in 13 runs and his play. The shortcuts are fast7 and lean7: release 30 s, fuse 13,000 MiB. What removed the old hangs is not shown.
- **His play on fast5 (section 42) [M]:** no hang in 185 s (the poll took 34 chunks back), available 462-548 MiB, but 62 s in
  frames over 100 ms; the container's fuse (12,400 MiB) was at its limit with memory free beside it, and orphans held 0.4-0.55 GiB.
- **A lean version stands beside (section 43):** binary without journal, traces and this experiment's catchers, nothing beside the
  emulator; boots, not yet played. The audit of redundant copies and mappings is section 44.
- **The zero skip without its hang (section 40) [M]:** with the poll before every submission (`BC5_GUARD_ZSKIP_POLL_SUBMIT`, arm fast5,
  build g412u) nine scripted runs had no ring timeout (3 of 9 before), about 650 MiB less pinned, lowest available 680-889 MiB
  against 283-384. Not yet seen: the picture, and his play.
- **Section 37's rule is refuted (section 39) [M]:** the GPU's command buffers and tables name the heaps without a GPU bit in 62 % of
  submissions; fast4 fed the GPU zeros there and is withdrawn. Pinning what is named takes back 1,114 of 1,180 MiB.
- **30 % of the direct memory file is all-zero pages (section 39) [M]:** 3,571 of 11,826 MiB in play; that sizes the zero-page scheme of section 31.
- **fast4 hung the GPU in his play (section 38) [M]:** ring timeout at 108 s, the ring reset failed, the box rebooted.
  The no-GPU-bit unpin is the first suspect [I]; it is not an arm for his shortcut as it stands.
- **The first change that moves the wall (section 37) [M]:** four heaps the title mapped without a GPU bit are no longer pinned
  (`BC5_GUARD_NOGPU_UNPIN`, arm fast4, build g412s): 1,024 MiB less pinned at the wall, lowest available 428 MiB instead of 283,
  no fault, no timeout, the zero buffer never written, in six scripted runs. Not yet seen: the picture, and his own load.
- What the pin is made of (section 34) [M]: in play the command buffers name 0.9 GiB of the 12.2 GiB under views; seven heaps, 5.9 GiB,
  are never named. Of those, heaps that by their purpose are the CPU's (audio, physics, components, assets: up to 2.7 GiB) are
  pinned for the GPU only because the title mapped them as direct memory; whether its GPU bits tell them apart is the next check.
- The GPU bits, checked (section 35) [M]: four heaps, 1,522 MiB under views and about 1.1 GiB pinned, carry no GPU bit and are never named by a
  command buffer; but F96 recorded a GPU fault inside one of them (Physics), so the bits alone do not prove the GPU stays out. A lead, not a fix.
- The zero skip's hang, caught (section 33) [M]: the skip learns of the title's writes by a poll; 45 chunks were found written with a mean of
  59 ms (up to 149 ms) and 1,204 submissions inside the window, and the run's GPU hang begins 4 ms after one such find in the
  index-and-vertex heap (32 ms, 15 submissions on zeros). The fix is to catch the first CPU write synchronously (section 31).
- His play of 19:40 (section 29) [M]: on his live save the pin is 11.84-11.89 GiB at two minutes, about 250 MiB above the scripted
  copy; from 103 s the box swaps (2,000-6,000 major faults/s, PSI full to 48 %), frames of 1-15 s, the last flip at 144 s.
  The memory wall is the first defect in his way; the speed work of sections 19-28 does not reach his play while it ends so.
- Speed after the table fixes (sections 18, 19) [M]: both fixes of the host's memory tables give about +47 % frames in the load phases
  (`KYTY_BC5_RANGES_FAST=1`, `KYTY_BC5_PHYSMAP_SORTED=1`; arm fast2, build g412i). After them neither the game thread nor the Render
  Thread is bound by host code (6-23 % of their time, no line over 4 %); they wait half their time, the Render Thread for the
  GPU at the flip and at label waits (30 %) and for the device mutex (12 %). The orphan release now cuts on his route without the
  zero skip (pin 11.5-11.65 GiB, was 12.0); the budget is still short at 215 s.
- The device mutex (section 20) [M]: every submission does all its host work under one mutex; it is held 45 % of the time
  (`bc5-ring` 23 %, Render Thread 14 %, `bc5-chainwd` 8 %), the three wait 35 s of 180 s for it, single holds reach 35-135 ms in most 10 s windows and 354 ms in the save load.
  Stage 0 (section 22): long holds lie inside 56 % of the frame gaps over 100 ms but cover 27 % of their time, so a shorter
  hold removes at most that share; not built (design: `DESIGN-device-mutex.md`).
- The frame gaps by cause (section 23) [M]: inside the gaps over 100 ms the flipping thread is 47 % on the CPU outside the host's
  GPU path (the title's frame work), 16 % in the host's submit path, 24 % blocked on the two submission mutexes, 6 % waiting for
  the GPU; the GPU's completion thread is idle 90 % of the gap time. The gaps are not the GPU and not the disk.
- Inside the gaps by function (section 24) [M]: the flipping thread's CPU time there is the title's own code (45 % of the gap time);
  our user-space code in the GPU path is 4 %, the other 12 % under the submit scopes is kernel time. Since 18:02 every fast2 run
  ends at 144-151 s (five of five, one without catchers): no memory line moved, the arm was always at the watchdog's threshold.
- The play phase (section 25) [M]: an ordinary frame is 37 ms because the title's CPU part (15 ms), the host's submission (8 ms) and
  the GPU's part (21-24 ms, of which the Render Thread waits 15 ms at the flip and at labels) run one after the other. The frames
  over 100 ms (16 % of the play time) are the host's long holds of the device mutex with the GPU idle; the title's threads spin in
  tight wait loops meanwhile. Not the TLB, not faults, not signals, not the cores, not the CPU's clock.
- The ordinary play frame, corrected (section 26) [M]: the host does not hold buffers back (handed to flushed: median under 1 ms);
  something is in flight on the GPU for 30 of the frame's 34 ms; the title calls the flip at 22 ms and waits 12 ms for the GPU.
  The GPU side is the long pole of the ordinary frame. The title's wait loops poll its own job system, nothing of the host's.
- The long play frames (section 27) [M]: the longest holds are direct sync under the device mutex right after the orphan release cuts
  memory that the title maps again seconds later (its AMM heap swings every 10 s; 96 % of what is cut comes back). The release's
  4 s idle time causes them; a longer idle time or a no-cut-again rule removes them at the price of the release's saving.
  The GPU runs at 1,850-2,150 MHz with 40 CUs (a console: 2,230 MHz, 36 CUs).
- The release against the long frames, measured (section 28) [M]: neither the return-aware rule (fast3) nor a 30 s idle time changes the
  long play frames or the pin beyond the run-to-run spread; with no cut at all (30 s) the pin is the same and 17 frames over 100 ms
  remain. The release is one trigger, not the main source; the previous line's last sentence is corrected by this one.
- The wall as arithmetic (section 16) [M]: at 165 s the guest pins 12,024 of 15,193 MiB; the 3,169 left hold the kernel, the
  GPU driver's buffers, the desktop and the emulator only with 986 MiB in swap and 42 MiB of file cache for the game. Over by
  about 0.4-0.5 GiB; 320 MiB of the pin are orphans (ours).
- Where the time goes (section 15) [M]: in the loads the game thread is a quarter to a third inside the host's AMM
  bookkeeping (linear range tables, 28,000 entries); one fixed loop (`KYTY_BC5_RANGES_FAST=1`, build g412f) gives 30 % more
  frames in both load phases. The disk delivers 2.2 times the bytes the title asks for. More of the same class is open.
- His plays of 11-11 (section 14) [M]: unstable on every build after the intro movies. Loads are CPU-bound on the game thread
  (the title's work plus the host's mapping work per layout change); from about 95 s the cgroup limit thrashes; with the zero
  skip the pin still reaches 11.6 GiB in 130 s, and the zero skip has now 2 GPU ring timeouts in 8 runs.
- Night of 11-10/11 [M]: with `memory.max` 12,400 MiB every arm survived; zero skip + orphan release (arm zo): 0.55-0.75 GiB
  less pinned, major faults 550-1,250/s -> 2-56/s, PSI full under 1 %, the pin flat for 6 of 12 minutes. One GPU ring
  timeout in five zero-skip runs. ASTRO BOT's host leak is 217-218 MiB/min, steady, with no input and with PLAY_CAPTURE off.
- ASTRO BOT's leak, fixed in a private build (section 11): the graphics events' unbounded pending queues. With
  `KYTY_BC5_EVENT_PENDING_CAP=64` the host's anonymous memory grows 0.1 MiB/min instead of 217.8 [M]; not played, not in the shared build.
- ASTRO BOT's leak (section 10): glibc arena memory of the completion thread `bc5-cq0`, through the soft CP's event
  fire into an unbounded `pending_events` queue and a second site in `completion_thread`; a bound on that queue is the fix candidate.
- The earlier lines below are the state before the night.

**Before the night: analysis, design, one build and two short plays (section 7): the ledger answered the split; no arm moved the wall.**
- After the plays (section 7): at his save the pin is 12.07 GiB and rising, 2.97 GiB of it the AMM heap, 0.48 GiB
  orphans; pinned pages are not unevictable and get unmapped under pressure [M]. "low" trims faults, not the wall.
  ASTRO BOT's kill is a separate thing: flat pin, 7.3 GiB of host anon in the shared build. Next: orphan release,
  an enforced pin cap, AMM by use, and per-process columns in the sampler. The lines below are the state before the plays.
- The 12 GiB is the title's own GPU heaps and streaming pool, pinned whole. It is not a leak and not duplicate views.
  What is excess against the console: 2.8–3.7 GiB of untouched zero pages [M], released memory that is never
  unpinned (size unmeasured while moving), a page-cache copy of the game's data, and the zram store.
- The slow frames are the game thread waiting on memory, not the GPU [M]. The likely mechanism is the kernel
  scanning 12 GiB it cannot free, swapping the title's CPU heaps into zram, and re-reading files [I].
- The first step is the ledger and the mlock of pinned ranges: both small, both low-risk, and the ledger decides the
  rest. The one measured lever stays the zero skip, with its hang risk.
- Open: the per-heap split at his current save; what in the game's state adds 0.35–0.8 GiB of pin and doubles the
  churn there (no older save exists to compare); whether link 2 holds on kernel 7.2.15.
