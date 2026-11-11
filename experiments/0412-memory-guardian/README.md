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

## Verdict

**After the unattended night (section 9): a cgroup memory limit keeps the box alive, and the zero skip with a list scanned at his save removes the memory pressure in scripted runs of his save; the frame rate there is GPU-bound and did not change. Not yet seen or played by him.**
- Speed after the table fixes (sections 18, 19) [M]: both fixes of the host's memory tables give about +47 % frames in the load phases
  (`KYTY_BC5_RANGES_FAST=1`, `KYTY_BC5_PHYSMAP_SORTED=1`; arm fast2, build g412i). After them neither the game thread nor the Render
  Thread is bound by host code (6-23 % of their time, no line over 4 %); they wait half their time, the Render Thread for the
  GPU at the flip and at label waits (30 %) and for the device mutex (12 %). The orphan release now cuts on his route without the
  zero skip (pin 11.5-11.65 GiB, was 12.0); the budget is still short at 215 s.
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
