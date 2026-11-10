# Audit 0406: memory safeguards that cost performance (laptop only, 2026-11-05)

Repo read: `C:\Users\kjani\Downloads\bc5\bc5-0401` (no git, no box). Sources: `docs/HANDOFF.md`, experiments 0288, 0330,
0356, 0358/0359/0361/0386/0388, 0379, 0401 (README series e7/e8, `*-notes.md`, `mk*.py`, `raw/night/r6c-*`, `r7m-*`),
`backend/kytyplus-patches/0001-bc5-lle-agc.patch` (P below, by line), `backend/src/direct.cpp`, `tools/bc5-mount/src`.
"Not found" means I looked and the laptop has no evidence.

## A. The e6 -> e7 drop (r6c 41.3 vs r7m 38.4 flips/s)

### What the records show (`experiments/0401-mesa-preamble-switches/raw/night/`)

- **The two summaries average the whole run, load included.** r6c: 41.3 over 1051 s, G 152. r7m: 38.4 over 1045 s,
  G 148. No per-window flips exist after G on the laptop. `route.txt` stops at G, and `probe.txt` holds crumb lines.
  So the steady-state gap is not measured.
- **Run order is confounded.** r6c ran at 05:59:54 and r7m right after it, at 06:17:49, in the same boot
  (`night.txt:203-207`). Then r7all hung. It is one pair, not interleaved and not repeated.
- **The same words run again vary by about 9 %.** The e8 "c" arms used one binary and one set of words at the same
  save, G+600: 34.7, 33.6, 32.9, 33.4, 33.9, 35.0, 33.3 and 31.9 (README e8 table). That is a spread of 3.1 flips/s.
  r6c minus r7m is 2.9 flips/s, inside that spread.
- **r7m was smoother than r6c on every other measure.**
  - Seconds with a gap over 100 ms: 181 against 219. Longest gap: 1.2 s against 3.3 s.
  - Time stalled under PSI full (cumulative ms in `memline`): r6c +62.9 s (117,648 → 180,609); r7m +5.2 s
    (180,659 → 185,839).
  - r6c sat at 11–43 % PSI full from 160 s to 410 s. r7m peaked at 8.5 % at 310 s.
  - If memory had decided the frame rate, r7m would have been faster. Either the gap is noise or order, or something
    in e7 costs steady CPU or GPU time.

### Code differences e6 → e7, and whether any is on a hot path

- **zsk (`BC5_DIRECT_ZERO_SKIP`, exp 0379 block).**
  - **No write protection and no fault takeback exist.** CPU writes are found by `lseek(SEEK_DATA)` over each skipped
    run at the start of every full sync (`0379-zero-skip/raw/zskip_block.cpp:267-298`, `zskip_take_back`). That is
    about 40 lseeks per full sync. The canary is a separate nice-10 thread: every 50 ms it clflushes one 2 MiB slice
    and scans it (`:153-165`), about 40 MB/s of flushes off the game thread.
  - The 42 CPU and 169 hint takebacks are one-time imports. A hint takeback runs in `direct_force` before the IB, and
    each one unmaps a canary piece (`zskip_release`) and maps the real chunk. They would show as gaps, but r7m had
    fewer gaps.
  - **The only mechanism with a measured precedent is BO-list growth.** F172 measured that 64 more BOs on every
    submission cost 10–15 % fps (+1.5 ms of CS ioctl a frame; `backend/src/direct.cpp:279-284`).
    - The skip splits the eager heaps: in exp 0379 B1 it added 28 BOs (121 against 93) and ~1,000 mappings
      (F542). F542 measured "no measurable host cost" and the same flips/s (35.4 / 35.4).
    - r7m's BO count is not on the laptop. Its direct.log has the `pinned … in N BOs` line.
  - Verdict: possible, but contradicted by 0379's A/B. Not shown.
- **lzr `30,dry`.**
  - A pass every 7.5 s on the sync path. It rebuilds covers over ~19,400 views, walks ~5,700 chunks and counts
    ~19,400 maps (`lzr0401-notes.md` §6). Nothing is cut and nothing is drained in dry mode.
  - Estimated at tens of ms every 7.5 s, which is ≤0.3 %. It is not measured.
- **Quiet journal (on in r7m).**
  - Each line costs one `vsnprintf` into a 1 KiB buffer, a text classification, and a mutex plus a ring copy if the
    line is dropped (`cap0401-notes.md:322-325`).
  - That is ~2.4k lines/s (r6c wrote 385 MB in 1,051 s). It saves 336 MB of writeback. Net: likely a gain.
- **cap's map caps, flx, the 19 tables, thb.**
  - The caps were off ("programs off, census off").
  - flx off, with crumbs on in both runs: one assignment per draw and FlDraw +~100 B (`flx0401-notes.md:263-273`).
  - Tables off: today's registration at init only.
  - thb (batch-1 held stubs unregistered while their tables are on, which they were in both runs) would print
    "stubbed import called" if the title called one (P:56620-56628). No arm printed it (README e7).
  - None of these is on a hot path at a measurable level.
- **Always-on in e7 with every switch off.**
  - zsk: a thread-local flag set and reset in `map_window`, and one getenv.
  - lzr: one static check per sync.
  - quiet: one flag test per line.
  - flx: one assignment per draw.
  - Nothing found anywhere near 7 %.

**My explanation:** most likely run-to-run variance plus run order. r7m ran second, in a box that had just run 17
minutes of r6c. My code reading found no e7 change that costs 7 %. Confidence: medium.
- If the gap is real, the best code candidate is the zsk BO split (the F172 mechanism). The next is lzr's 7.5-s pass.
- Check it with no new build:
  1. Read r6c's and r7m's direct.log on the box for the `pinned … in N BOs` line, the `timing split` (sync/hint ms
     per 128 submissions) and the `learned apply:` lines.
  2. Run interleaved pairs at the same save on d5d67456 alone: zsk on/off with lzr unset. Run 3 pairs, ABBA, and
     compare flips/s from G+120 to G+900, not over the whole run.

## B. Per item

Format: guards against / added by → evidence → overlap → cost → verdict (confidence) → restore value.

1. **`BC5_DIRECT_EAGER_NAMES` (9 heaps incl. AMM).**
   - *Guards against / added by:* GPU-only pages never imported. A GPU fault is a 14-s freeze and a reopen (F88), and
     it has taken the machine down (F207). Added by exp 0042 / F96.
   - *Evidence:* F96, runs 100–112. It is still the reason the render heaps cannot go lazy (lzr notes §2).
   - *Overlap:* zsk removes the zero part of the two biggest heaps.
   - *Cost:* the eager list pins 10,047 MiB, 90 % of what is pinned (F353). 2.8 GB of the two big heaps is all zero
     (F394, F402).
   - *Verdict:* **keep**, and use zsk as its trim (high).
   - *Next:* extend the zero scan (`BC5_DIRECT_ZERO_NAMES`) to `AMM` and `RenderGpuRwLarge`. Their zero share is not
     measured (not found).
2. **`BC5_DIRECT_ZERO_SKIP` (exp 0388 list, 1,014 MiB in 40 runs).**
   - *Measured:* GTT −440 MiB and swap −739 MiB in r7m. F541: −1.9 GB on the bench at the same flips/s.
   - *Risk:* canary hits (F542, 11 in 37 min with the older list). Lost GPU writes until the watcher sees them, up to
     ~2 s.
   - *Cost:* the CPU cost is listed in A. A device reopen re-pins ~0.9 GB at the worst moment.
   - *Verdict:* **keep** (high on memory, medium on fps until the A/B above).
   - *Restore:* unset it.
   - *More gain:* exp 0379's own list held 2.6 GB. The moving list dropped the hit runs, so a fresher intersection
     could win back several hundred MiB.
3. **`BC5_DIRECT_LAZY_NAMES` (orbis_user_malloc, Wwise, SoundAlloc, FileSystem, UIStringAlloc).**
   - A saving, not a cost: −242 MiB at the same fps (F394, exp 0330 arm C).
   - *Verdict:* **keep** (high).
4. **`BC5_DIRECT_REMEMBER_UNMAPPED=1` (exp 0103, P:33774).**
   - It saves a 9 ms walk a frame (run 372).
   - Memory: one `std::map` of pages.
   - *Verdict:* **keep** (high).
5. **`BC5_DIRECT_AMM_PRT=1` (exp 0102, P:28628).**
   - *Guards:* the UI layer's sparse tiles (F161).
   - *Cost:* the GPU page tables for a 64 GiB PRT window. Their size depends on whether amdgpu uses 2 MiB PDE-as-PTE
     for PRT (~256 KiB) or 4 KiB PTEs (up to 128 MiB, likely in VRAM). Not found; TODO(verify) with
     `amdgpu_vm_pt.c` or VRAM use with and without it.
   - *Verdict:* **keep**, verify the cost once (medium).
6. **`BC5_DIRECT_DMA_SNAPSHOT=4096` (exp 0122, F172).**
   - *Guards:* stale CP-DMA staging (menu text, F146/F172).
   - *Cost:* one 64 MiB USWC GTT ring (`direct.cpp:285-330`), always in the BO list, plus a memcpy of ~1.5 MB a frame
     (~60 MB/s).
   - The per-slot version cost 10–15 %. The ring version measured "no measurable cost" (F172).
   - *Option:* `kSnapRingBytes` 64 → 32 MiB would free 32 MiB. It needs a build and an overflow-count check.
   - *Verdict:* **keep**; shrinking the ring is a small candidate (medium).
7. **`KYTY_BC5_ALL_RW=1`, `KYTY_BC5_DMABUF=1`.**
   - Architecture (ADR 0006, `kytyplus-patches/README.md:71,105`). No memory cost of their own.
   - The private-recommit memset zeroes only data runs of the private memfd (P:25015-25025). That is correctness,
     and it is cheap.
   - *Verdict:* **keep** (high).
8. **`KYTY_BC5_CACHE_MIB=96,16,16,16`, `KYTY_BC5_VMA_BLOCK_MIB=16`.**
   - Savers: 1.15 → 0.12 GiB of GTT (F47).
   - Staging 96 MiB serves only the presented frame. 48 might do, a ~48 MiB gain, untested.
   - *Verdict:* **keep**; lowering staging is low priority (low).
9. **`KYTY_GUEST_MEMORY_MB=13824` / `KYTY_BC5_MEMORY_FROM_PARAM=0`.**
   - The memfd is sparse, so the unreserved part costs nothing (F353).
   - 12288 does not start (F394). Param mode would give 12,460 MiB of direct memory, below today's (mem0401 notes).
   - *Verdict:* **keep both as they are** (high).
10. **`KYTY_BC5_AMM_PRT_CMDS=1` + `KYTY_BC5_AMM_EXTRA_CMDS=1` (mkamm0401, series e4).**
    - *Confirmed by code:* with either on, every AMM map and unmap, including the title's plain ones, goes through
      one recursive mutex and a `std::map<va, Bc5AmmPage>` with one node per 16 KiB page (`mkamm0401.py:158,
      357-360, 516`; notes :105, :242).
    - The title imports none of the 26 NIDs (`amm0401-notes.md:3-5`, prtvo0401 item 7).
    - *Cost* (reasoned): ~80 B per page, so ~16 MiB for the ~3.1 GiB AMM pool (~60 MB at 12 GiB, per the notes),
      plus malloc churn at ~4k AMM maps and unmaps a minute (exp 0288 table).
    - It was on in both r6c and r7m, so it is not part of the e6 → e7 gap.
    - *Verdict:* **drop-candidate for this title** (high).
    - *Restore today's path:* unset both, or set them to `0`.
11. **`KYTY_BC5_AMPR_WAITS=1`.**
    - No page table and negligible memory: 256 counters.
    - With it on, the `_04_00` counter records stop being no-ops. That is a behaviour change, not a memory one.
    - *Verdict:* **keep**, pending a check that the title does not use `_04_00` (not found).
12. **`KYTY_BC5_JIT_SHM=1` (mkjit0405).**
    - Reached only through three registrations (`jit0405-notes.md:14-17`). Its cost is zero unless the title calls
      them (not found).
    - *Verdict:* **keep** (high).
13. **R3 mem group (mkmem0405: M1/M21/M3/M7/M6/M20/M26/M30).**
    - Every item works on an error or edge path (gaps, holes, NULL, find-next end). No hot-path cost.
    - RELEASE_HOLES and MUNMAP_HOLES let releases succeed where they used to EXIT. Nothing is punched, though (see
      item 17), so they free no RAM.
    - *Verdict:* **keep** (high).
14. **lzr `30,dry` (mklzr0401).**
    - It has answered its question: 170 MiB idle under no view, 98 MiB of it releasable (README e7).
    - A live lzr frees ≤0.1–0.17 GiB. Each cut drains the GPU, and a failed re-import risks a VM fault.
    - *Verdict:* **drop the dry pass** (high). A live `30` is low priority (low gain × medium risk).
    - *Restore:* unset it.
15. **Journal: `BC5_DIRECT_JOURNAL_QUIET` (mkcap0401 edit 5) / `BC5_DIRECT_TIMING`.**
    - Measured: 385 MB of r6c's journal against r7m's 24 MB.
    - The journal's writeback evicts the title's pages: 309 against 30 MiB swapped and 45.7k against 3k major faults
      in 5 min (F353, normal against lean).
    - *Verdict:* **keep quiet on** (high). Unsetting `BC5_DIRECT_TIMING` as well removes the formatting, but loses
      the timeout ring.
16. **Learned-fault windows and `learned_apply` / `scratch_fill` (exp 0037/0156, P:29560-29760, :33845).**
    - *Guards:* a GPU fault at a known address (14-s freeze).
    - *Cost* (exp 0288): 107 windows of 96 MiB, 46 of them at junk addresses. 3.9 GB is "asked" in the first
      minute, much of it inside eager heaps anyway.
    - **`learned_apply` ran 10,028 times, 83 s of a 1,742-s session (4.8 %), and the direct syncs took 180 s, all on
      the game thread.**
      - It runs at every layout-generation change. Each run copies and sorts the whole mapping list.
      - zsk's ~1,000 canary mappings make that list longer.
    - *Overlap:* exp 0156 removed the quadratic part. No later fix of the per-change cost was found.
    - *Verdict:* **top candidate for CPU** (medium):
      - prune the 46 junk entries;
      - let `map_window` skip windows that lie entirely inside eager heaps (they change nothing there; exp 0379
        design);
      - read r7m's `learned apply:` lines first.
    - *Restore:* the old learned file.
17. **No hole punch on release (P:25008-25012 comment; lzr notes §4.5).**
    - *Guards:* stale imported BOs.
    - *Cost:* memory the title releases stays in shmem. Shmem was within ~74–350 MiB of pinned + private (exp 0288
      Q2), so ≤0.35 GiB.
    - *Option:* punch only unimported chunks on release. That needs code.
    - *Verdict:* **candidate, low priority** (low).
18. **Mount: `MALLOC_ARENA_MAX=2`, `BC5_MOUNT_DISK_CACHE`.**
    - The arena cap saves ~100 MiB (F353): **keep**.
    - The disk cache saves decode time (F167). Its data file is read buffered (FADV_RANDOM only, `io.rs:152-176`),
      and FUSE keeps its own copy (`FOPEN_KEEP_CACHE`, `fuse.rs:269`). So decoded data can sit in the page cache
      twice.
    - `POSIX_FADV_DONTNEED` after each disk-cache read would leave one copy. Gain and loss are both unmeasured: a
      FUSE miss would then go to NVMe.
    - Mount RSS of 700–850 MB is unexplained beyond a 32 MiB block cache (F353 asks for a heap profile).
    - *Verdict:* **experiment candidate** (low-medium).
19. **JobArenaFix.** A crash workaround (0359/0361), with no memory role. Off in his play, so no cost. Exp 0388 arm F
    is the host candidate.
20. **AMM fault ledger (exp 0356).** Not in patch 0001 or in any 0401 edit script (grep: 0 hits). No cost in the
    current binary.
21. **GDS clear / other memsets (P:4871, :34757, :21524).** One-time at init (GDS buffer, a 16 KiB submit area, a
    probe page). Negligible.
22. **Canaries.** zsk's canary is the only memory canary: one 2 MiB slice per run, 80 MiB with 40 runs, all zero
    pages. With a sealed memfd those pages are allocated only if written. P:35210 is a stack canary in a struct read,
    not a cost.

## C. Ranking (likely gain × low risk)

1. **Turn `KYTY_BC5_AMM_PRT_CMDS` and `KYTY_BC5_AMM_EXTRA_CMDS` off** for the second title: ~16+ MiB and a lock per
   AMM map, no behaviour the title uses. Restore by setting them to `=1`.
2. **Drop lzr dry** (unset `BC5_DIRECT_LAZY_RELEASE`): its question is answered, and it removes a pass every 7.5 s.
3. **Keep zsk and quiet**, and settle the 7 % with interleaved ABBA pairs on one binary. Read the r6c/r7m direct.log
   BO counts first.
4. **Learned windows:** prune the junk entries and skip windows inside eager heaps. This is a CPU gain of up to ~5 %
   of the game thread (exp 0288), at medium risk.
5. **A fresher, larger zero list, and zero scans of AMM and RenderGpuRwLarge:** possibly several hundred MiB, with
   canary-hit risk.
6. Smaller items:
   - the DMA snapshot ring 64 → 32 MiB;
   - staging cache 96 → 48;
   - the mount's double page cache;
   - punching unimported released chunks.
