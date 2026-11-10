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

## Verdict

**Analysis, design, one build and two short plays (section 7): the ledger answered the split; no arm moved the wall.**
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
