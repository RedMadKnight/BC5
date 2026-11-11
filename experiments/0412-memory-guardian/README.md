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

## Verdict

**After the unattended night (section 9): a cgroup memory limit keeps the box alive, and the zero skip with a list scanned at his save removes the memory pressure in scripted runs of his save; the frame rate there is GPU-bound and did not change. Not yet seen or played by him.**
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
