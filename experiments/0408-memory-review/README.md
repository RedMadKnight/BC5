# 0408 — a second, skeptical review of the memory analysis (exp 0406, 0407, the AMM-pool note, the top session's conclusions)

**Status: laptop review done, 2026-11-06. No box access, no code, nothing installed.** Written on the top session's
order, for the maintainer, who is not convinced by exps 0406 and 0407. It starts from the records, not from their
conclusions.

**Question.** Which of the recent memory claims hold, which are weak or wrong, what did their authors miss, and what are
the actual causes of "RAM chokes and play got worse since 10-21"?

**Setup.** Laptop only. Read: `docs/HANDOFF.md` 029e0d6b (F-rows), the four reviewed documents at their commits
(0406 f3f8803f, 0407 uncommitted on `exp/0407-ps5-memory-model`, `ammpool0401-notes.md` 859c8aad, exp 0401's README
and `hang1954-0401.md` at 859c8aad), exp 0401's `raw/night/*` (1,328 files), its `raw/night-arms-*.txt` (the exact
words of every arm), the coordination copy of `play-pkg.sh`/`bc5-run.env` (2026-10-30) and exp 0396/0399's manifests,
main's patch 0001 and `backend/src/direct.cpp`, and the public clones under `Downloads/bc5/refs/` (KytyPS5 09753bf,
Mesa ab2374a). `memsum0408.py` re-derives the memory numbers of every night arm from its `*-memline.txt` and
`*-summary.txt`; its output is `raw/night-memory-table.txt`. Numbers below marked *(re-derived)* come from it.

## Result

### A. The one table that matters (re-derived from exp 0401 `raw/night`)

Route arms at his slot-4 save, standing still, RT on, all in boot 9af31fd4 (11-05 06:40 → ), same route runner:

| Arm set | Binary | Zero skip | GTT at t 10 s | GTT max | swap max | MemAvailable floor (G+120..) | PSI full, s per run | flips/s (whole run) |
|---|---|---|---|---|---|---|---|---|
| e8c1..c8, e8f1..f8 (16 clean of 18) | e8 dc7fb4e0 | **on** | 7,580–8,290 | 12,356–12,419 | 806–1,023 | 292–376 | 2.6–8.9 | 31.3–35.0 |
| e9n1..n3, e9g1 (4 clean) | e9 de6a0ad5 | **off** | 8,860–9,024 | 12,854–12,913 | 1,709–1,772 | 182–236 | 71–112 | 32.5–34.6 |
| e9z1 (F403 at G+177) | e9 | on (+copy-back) | 8,256 | 12,348 | 1,402 | 279 | 9.3 | — |
| r7m (e7) | e7 d5d67456 | on | 8,073 | 12,427 | 966 | 279 | 5.2 | 38.4 |
| r6c (e6) | e6 7252558e | off | 8,749 | 12,867 | 1,705 | 189 | 63 | 41.3 |

The e8 and e9 words differ only in the zero skip (+ `LAZY_RELEASE=30,dry`, a counter), `FL_CRUMBS`, and e9's two
default-off 0406 lines (`raw/night-arms-e8.txt:5` against `raw/night-arms-e9.txt:7`; the switch-line diff is in §C4).

Two facts fall out of it that none of the four documents states:

1. **The zero skip is worth ~500 MiB of GTT, ~750 MiB of swap and a 10× lower PSI-full total at this save, in the same
   boot** (e8 against e9 normal; r7m against r6c agrees). The maintainer's shortcut runs **without** it (0401 README,
   "Series e9": "without the zero skip, by his choice"). The pressure he reports — MemAvailable ~200 MiB, swap 1.7 GiB,
   PSI full 40–60 % — is the e9-normal row, and his own 11-04 19:58 play curve (`hang1954-0401.md` §4: GTT 12,987–13,003
   of 13,312, swap 1,715, PSI full 61 %, floor 161 MiB) is the same row with the title moving through new areas.
2. **At a standing bench, that 10× memory-pressure difference did not move flips/s at all** (e8 31.3–35.0 against e9
   32.5–34.6). So the route arms, which stand still after G (0401 README "Series e7": "no walking keys"), are the wrong
   instrument for the memory question. The frame-rate cost of memory pressure appears only when the title streams:
   F620 (r = −0.84 with mount reads), F689 (r = −0.93; slow minutes follow PSI *io*, not PSI mem). Every A/B that
   wants to show a memory gain in frames must walk.

Also from the table: the **old save and the new save differ by ~800 MiB of GTT on the same binary** (r6 e6 at the old
save 4b6b1ea5: GTT max 12,054, PSI 2 s, 51.1 flips/s; r6c e6 at the new save 558115f3: 12,867, 63 s, 41.3). Every
"e6 against e7" or "normal against lean" number is only valid within one save.

### B. The reviewed claims, verdict by verdict

Scale: **holds** / **weak** (not shown either way, or shown only under a confound) / **wrong**.

#### B1. Exp 0406, the safeguard-cost audit (f3f8803f)

| Claim | Verdict | Evidence |
|---|---|---|
| Host CPU on the render thread does not set the frame rate (F482, F483, F470) | **holds, with its scope** | Three measurements agree (F483: −80 % `emit_prefix` → 33.8 vs 33.6; F470: two host cuts, 33.7 vs 33.8). The scope is the *render* thread at a ~30-flips/s scene. It says nothing about game-thread stalls (`learned_apply` up to 633 ms, exp 0288) or about I/O, which 0406 itself keeps as the real levers. |
| The e6 → e7 drop (41.3 → 38.4, −7 %) is noise | **weak** | The spread argument is sound (e8 "c" arms 31.9–35.0 at one binary). But the confound runs the *other* way: r7m had a tenth of r6c's PSI-full time and 740 MiB less swap, so if memory had any effect r7m should have been faster. "Noise" cannot be told from "a real e7 cost partly hidden by the memory gain". 0406's own proposed check (r6c's and r7m's `pinned … in N BOs` and `timing split` lines, a box read) is the right one and has not been done. The whole-run averages also carry different loads (G 152 vs 148, fine here). Unresolved, not noise. |
| The ranked drop list | **holds for items 1–3 and 9, weak for 6** | Item 1 (`ACB_INHERIT=journal`): 0 lines in every arm, census empty — a catcher with nothing to catch, drop. Item 2 (R3 catchers): answered. Item 3 (AMM PRT/EXTRA words): the title imports none of the 26 NIDs; the per-page `std::map` and page table are small (~16 + ~60 MiB) but real. Item 6 (`GPU_CHECK_PRODUCT`): ~1 % reasoned, never measured, and it is an RT-on guard — correctly gated on an RT-on A/B. Item 4/5 (probe copy, learned windows): costs cited from exp 0288 (10-24) and never re-measured; medium is fair. |
| "FL_CRUMBS was the one switch present in every slower all-on arm" | **weak** | sall 22.8 vs s0 23.4, tall 22.9 vs t0 23.6, t6all 22.0 vs t6 22.8: 2–4 % on 90-s start arms whose own spread is 22.9–24.6 (e4) and 22.8–23.9 (e6). Not evidence. |
| The lean profile (built from 0406) failed 2 of 4; exp 0401 blames the late-producer wait | **holds (medium-high), and lean's gain is unproven** | e9l3 and e9w1: the same title address 0x930003d83, the same stack, a write to 0; 2 of 5 arms with `WAIT_LATE_PRODUCER_MS=250` against 0 of 24 without, in one boot; the wait acted 2–10 times in each of those arms. The wait was not a 0406 item; lean carried it by the top session's addition, and the e9 results section first left it out of lean's list (corrected in "e9w1 is e9l3's crash"). The other lean failure, e9l1 (a shader reading page 0, F686's near-class), came on normal too (e9n4), so it is not lean's. What remains: lean's +4 % (34.8, 35.4 vs 32.5–34.3) is inside the ±5 % 0406 itself defines, and only two clean lean arms exist. Lean minus the wait has not been bisected (the planned e9d/e9p/e9u arms never ran). |
| Lean's page-0 GPU hang is attributable to lean | **wrong** | e9n4, normal words, same class (SQC instruction fetch at 0, vmid 7). Both are F443's family. |

What 0406 missed: (i) the zero skip is the largest memory lever already measured and it is *off* in the shortcut it
audits — 0406 lists the skip under "kept" by its r7m numbers but never says the shortcut lacks it; (ii) the standing
route cannot show memory in frames (§A.2); (iii) `BC5_DIRECT_AMM_PRT=1` is in the launcher (`play-pkg.sh:91`, the
coordination copy; exp 0396/0399 manifests line 42/43), which 0406 lists as "keep" without its page-table cost and
0407 could not confirm from the laptop.

#### B2. Exp 0407, the PS5 memory model (uncommitted)

| Claim | Verdict | Evidence |
|---|---|---|
| Pinning is console-like | **holds as reasoning; it is inferred, as the README says** | No public source either way. Every open emulator commits eagerly; AnyPS5, our closest relative, *refcounts* udmabuf chunks per guest buffer and drops them (its `GuestBufferMemory.cpp:641-655`), so "pinned for the run" is our choice, not the only console-like one. |
| The RAM gap = reserved-but-materialised (zero chunks) + released-but-kept + page cache | **holds in parts; incomplete** | Zero chunks 3.4–3.7 GB (F394, measured). Released-kept ≤ 0.35 GiB (exp 0288 Q2, measured: small). Page cache (F620/F689, measured). **Missing:** (a) the GTT ceiling, 13,312 MiB (`ttm.pages_limit`, D12): his 19:58 play reached 13,003; (b) the import is monotone (nothing is released, P:25011, F623), so any long moving play climbs to that ceiling — the gap is *time- and scene-dependent*, not a fixed number; (c) RT on's share: bench A1 11,992 MiB RT on (exp 0379) against 11,378 imported RT off (F394), +145 MiB/min growth above the RT-off plateau (F505) — about +0.6 GB that is not "reserved-but-materialised". |
| Ranked plan: L1 learned trim | **holds as low-risk; its gain is unmeasured** | The windows' RAM outside the eager heaps is "≤ 0.7 GB (inferred)". F353 says the 61 real windows ask 3.9 GB at every start, most inside eager heaps. The file grew 107 (exp 0288, 10-24) → 109 (F468, 10-28) → 110 lines (exp 0395, 11-02): +3 windows, ≤ 288 MiB, not a trend. Cheapest decisive test in §E. |
| R1 release punch | **holds; low value** | ≤ 0.35 GiB for memory.cpp surgery plus a BO-split path (exp 0333 phase R's problems). Last on the list, not second. |
| P1 protection census | **holds** | Log only; the right precondition for replacing the name lists. |
| Z2 zero skip v2 | **weak** | Its premise is that take-backs under a running job cause F403. e9z1 hung F403 with *no* canary hit (25 take-backs, all by CPU writes, the last 36 s before). Both e8 F403s followed a canary take-back within 0.11 s. So the association is 2 of 3, and (a) is a guess, as the README says. F403 so far: 3 in 19 arms with the skip on, 0 in 10 without (0401 "e9z1"). Z2 is a redesign of a mechanism whose plain form is already measured; its risk column is honest. |
| N1 null BO instead of NULL PRT | **holds as a hazard; not shown to matter** | Mesa ab2374a `ac_gpu_info.c:437-442` says exactly what 0407 quotes (GFX10–12: SMEM load on a NULL PRT page → VM fault and hang); RADV's `radv_amdgpu_bo.c:144-181` is the workaround. `BC5_DIRECT_AMM_PRT=1` **is** in the launcher (`play-pkg.sh:91`), so the hazard is live. But F403 records no fault, and e9n4/e9l1 fault at page 0, not in the AMM window. Cheap and harmless; not a RAM lever. |
| The cited sources and file:line | **holds** | Checked on main 029e0d6b: P:24897/24905 (memfd, seal), P:24962–24979 (1 TiB private file), P:25008–25025 and P:25011 (no punch), P:28631 and P:32769 (PRT window on `AMM_PRT` presence), P:28698–28710 (`kDChunk`, `kDMaxBo`), P:28757/28783 (lazy/eager names), P:28990 (eager loop), P:29047 (merge cap), P:29213 (`direct_force`), P:29500–29545 (aliases), P:29546–29548 (96 MiB window), P:33845 (`learned_apply` from submit), P:38829–38845 (AMM borrow); D:826, D:886–896 (`AMDGPU_VM_PAGE_PRT`), D:911. KytyPS5 09753bf `memory.cpp` 68–74 (12,800 MiB budget; the README says 68–70, off by a few lines), `memory.h:45–46`. All as cited. |

What 0407 missed: the ceiling and the growth (above); that `AMM_PRT` is on; that the eager heaps' zero share is
already addressed by the skip that is switched off; and that a plan ranked "by RAM gain" has its largest measured
gain (the plain skip, −500 MiB) outside the plan and its first item unmeasured.

#### B3. The water session's AMM-pool note (`ammpool0401-notes.md`, 859c8aad)

| Claim | Verdict | Evidence |
|---|---|---|
| The 18:14 fatal was fragmentation, not exhaustion | **holds for the pool; the borrow side is not shown** | The 18:14 trace line (0401 README:98): "map of 0x4000000 bytes refused, 9653 maps hold the pool, 0xd444000 free" — 212 MiB free, a 64 MiB map refused: the free list had no 64 MiB hole, which is fragmentation by definition. But the map is refused only after the *borrow* from direct memory also fails (`AllocateAmmAutoDirectMemory`, base:1641-1643), and the note's own open question 1 admits the free direct memory and its largest block at 18:14 are unknown. So "the pool was fragmented" is shown; "the direct memory could not lend 64 MiB contiguous" is the second half, and with 1,120 MiB less direct memory under `FROM_PARAM=1` that half is exhaustion of the *borrow* headroom. Both halves are needed for the fatal. |
| Recommend `KYTY_BC5_AMM_SCATTER=rescue` | **holds as a fix for the fatal; it fixes a problem nobody needs to have** | The fatal exists only with `FROM_PARAM=1`, and `FROM_PARAM=1` gains ~120 MiB pinned (README:94). The simplest fix is `FROM_PARAM=0`, which is installed. Scatter is sound (upstream KytyPlus 3eee96a `ReserveAutomatic`/`MapAutomaticMemory` do it) but adds host mappings and views (F89), and open question 5 (piece count, TLB cost) is real. It is worth building only if `FROM_PARAM=1` is wanted for its own sake. |
| The trace/README consistency | **holds** | README:93 (the inference from 21,234 against 28,810 maps) and :98 (the trace) agree; the note's §1 reads the code correctly (checked base:1628-1659 by the note's own line numbers against patch 0001's `libAmpr.cpp` region). |

#### B4. The top session's conclusions

**(a) `KYTY_BC5_MEMORY_FROM_PARAM` made the "very smooth" play, and turning it off brought the choking back: wrong.**

- The times in the brief (16:58 on, 17:18 off) do not match the record. The README dates the smooth play 17:55:24–17:58:00
  (e2, `FROM_PARAM=1`) and the off play 18:16 (681 s). No play log is on the laptop (e2's launcher kept only
  `play-last.log` until the e4 launcher, README:118), so the brief's times cannot be checked here. The box's
  `~/bc5-data/captures/play-20261103-*` directories would settle it.
- The smooth play lasted **155 s** and ended in the AMM fatal. At 155 s the title has barely finished the load
  (F353: the pinned plateau comes at ~161 s; GTT in every route arm is still rising at t 150). A 155-s play cannot show
  memory choking because the memory is not yet full. The 18:16 play ran 681 s and collapsed "in its last seconds";
  his 19:58 play on 11-04 collapsed from 430 s on. The two differ in length first.
- The README's own comparison over the first 155 s (28.8 flips/s and 38 gap-seconds against 22.2 and 61 at 16:07) is
  a comparison against a play that was the first after a hang on series c with the acb prefix off, on a different
  route through the menus. The README's own reading is "the journal cannot pin the cause" (:94).
- What *did* differ in the smooth play: 7,500 fewer AMM maps in 150 s, consistent with refused maps (README:93),
  which means content the title asked for was not loaded. Less loaded content is lighter and smoother. Nobody
  recorded whether anything was missing on screen.
- The pinned gain was measured: 11,588 against 11,710 MiB at 150 s, ~120 MiB (README:94). The direct-memory size is
  address space; untouched pages cost nothing (F353 Q2). `FROM_PARAM` is not a RAM lever.
- What else changed between the smooth play and the worse ones: binary e2 → e2 (same) → e6 (11-04 18:56) → e8;
  JobArenaFix was turned off by the maintainer in the F2 menu after the 18:16 play (README:101) and is on in every
  night arm; the saves moved (4b6b1ea5 → 558115f3 on 11-04 20:04, a heavier scene by ~800 MiB, §A); the boot changed
  (11-05 06:40 reboot); e4–e8 added ~60 switch words, of which the AMM PRT/EXTRA per-page map (~16 MiB + ~60 MiB page
  table) and the table catcher's hashes are the only memory items.

**(b) The four older mechanisms as the maintainer's "old memory rebuild": none changed since 10-21.**

| Mechanism | Since | Changed since 10-21? | RAM today |
|---|---|---|---|
| One memfd through udmabuf (exp 0017/0023, ADR 0006) | early October | no | the pinning itself; console-like per 0407 |
| Eager heap imports (exp 0042/0066) | early October | the **lazy** list grew on 10-26 (F394/F395: Wwise, SoundAlloc, FileSystem, UIStringAlloc; −242 MiB) — a gain | 10,047 MiB eager, 2.8 GB of it zero (F353, F394) |
| Aliases (exp 0056) | mid October | no | 0 (second VA mapping of the same BOs) |
| Learned windows (exp 0156–0160) | ~10-18 | +3 windows (107 → 110 lines) | ≤ 0.7 GB outside eager heaps, unmeasured |

If "an area mapped separately within some frame" means something else, the candidates with a per-frame or
separately-mapped area are: the DMA snapshot ring (exp 0122, F172, 10-18: every graphics-buffer DMA source copied at
submission into one shared ring, 32 MiB), the hole scratch BO (one 2 MiB zero BO mapped over every hole, exp 0288:
1,975 maps, 8,096 MiB of VA, no RAM), the canary slices of the zero skip (one 2 MiB per run), the GDS shadow (+0x8000,
FL crumbs), and the AMM PRT window (64 GiB of VA, no RAM). None of them pins more than tens of MiB. The top session
should ask him which one he means; the answer changes nothing in §D unless it is a mechanism not on this list.

**(c) One e10 build = the AMM fix + 0407's five changes: wrong as a plan.** It fixes a fatal that only `FROM_PARAM=1`
causes (a switch worth ~120 MiB), carries a zero-skip redesign (Z2) whose premise is 2 of 3, and spends memory.cpp
surgery (R1) on ≤ 0.35 GiB, while the one measured lever (the plain skip) sits unused in his shortcut and the one
question that decides the ranking (what the learned windows pin outside the eager heaps) is a one-arm measurement.
See §D.

### C. What everyone missed: the confounders, listed

1. **Play length and the plateau.** The pinned import climbs for ~160 s, then grows with every new area (F353, F623)
   and never releases. Short plays are smooth; long plays reach the 13,312 MiB ceiling (his 19:58 play: 13,003).
   Any "smooth" verdict on a play under ~5 minutes is about the load, not about memory.
2. **The save position.** ~800 MiB of GTT between the two slot-4 saves on the same binary (§A). The night series
   switched saves on 11-05 05:50 (0401 "Series e7", try 1). Arms before and after do not compare.
3. **The zero skip's presence.** On in r7m, e8 and e9z1; off in r6c, e9 normal/lean and his shortcut. It is the
   largest single memory difference in the whole record and is not named as a variable by 0406 or 0407.
4. **RT on.** His 10-21 "ideal" play ran with the reflection traversals skipped in the launchers (F250, Q11: the
   skips stayed in the launchers after the 10-21 machine-down); RT became default-on on 10-24 (F343) and mandatory
   for tests on 10-28. RT on costs ~+0.6 GB of GTT and +145 MiB/min of growth (F505, exp 0379 A1 against F394), and
   is the regime of every "deepest memory pressure" record (F621, 10-29). The choking is **not** new since 11-03: F621
   (10-29) already has MemAvailable 0.19–0.37 GB, swap 1.0–1.7 GB, PSI full 23.6 %.
5. **Standing still.** The route arms do not stream, so they cannot show memory in frames (§A.2). The maintainer walks.
6. **Cold cache and run order.** r6c ran first in its boot (cold) and was *faster*; the first two e7 start arms were
   slow (119–122 s to the list) and 0401 reads that as a cold start. Order confounds exist but do not explain the
   e6 → e7 direction.
7. **Ring resets in the boot.** e8's 13 arms after one or two successful resets ran clean and alike; no memory
   effect of a reset is visible in the table.
8. **The mount's second page-cache copy.** `BC5_MOUNT_DISK_CACHE` (F167) is in the launcher and "at its 8 GiB limit
   since 10-25" (F689); decoded blocks then sit in the page cache twice (FUSE's and the cache file's; 0406 item 18).
   F814 says a bigger cache gave no frames. Whether *no* cache gives frames under today's pressure is untested.

### D. The top three actual causes of the RAM pressure, ranked

| # | Cause and evidence | Confidence |
|---|---|---|
| 1 | **The eager import's monotone growth with RT on reaches the 13 GiB GTT ceiling in any long, moving play.** Pinned ≈ 11.4 GB at the plateau RT off (F353), +0.6 GB RT on, then +145 MiB/min with new areas (F505, F623), nothing released (P:25011); his 19:58 play hit 13,003 of 13,312. Once GTT is within ~1 GB of the ceiling, the page cache is gone, every streamed asset is a re-read over a PCIe 2.0 ×2 NVMe, and frames follow the reads (F620, F689). | **High** for the mechanism (five independent records: F353, F505, F621, F623, the 19:58 curve); medium for RT's exact share (+0.6 GB is bench-to-bench, not an A/B). |
| 2 | **The zero skip is off in his shortcut.** −500 MiB GTT, −750 MiB swap, 10× less PSI-full at the same save and boot (§A). Its trade is F403: 3 in 19 arms with it, 0 in 10 without; e9z1 says the canary take-back is not the whole mechanism. | **High** for the memory numbers (16 against 4 arms, one boot); medium for the F403 link. |
| 3 | **The scene and the session got heavier, not the host.** +800 MiB between the two slot-4 saves on one binary; his plays run 10–35 minutes and stream; the 10-21 "ideal" play was RT off in effect and at an earlier point of the game. | **High** for the save delta; medium that it is what he feels (his wording, not a measurement). |

Not in the top three, with the reason: `FROM_PARAM` (~120 MiB, §B4a); the learned windows (≤ 0.7 GB, unmeasured, +3
windows since 10-24); the e4–e8 ports and catchers (tens of MiB; the AMM PRT/EXTRA page map is the largest); the
journal (385 MB a run before `JOURNAL_QUIET`, now 24 MB; a page-cache load that is already gone from his shortcut);
released-but-kept memory (≤ 0.35 GiB); the aliases and the PRT window (0).

### E. The cheapest decisive measurement for each open question

| Open question | Measurement | Cost |
|---|---|---|
| Is his choking the e9-normal row (no skip) or something else? | Read the `memory (exp 0401)` lines of his last three plays' `direct.log` (e3+ writes them every 10 s) and plot GTT, swap, PSI against the e8/e9 rows in `raw/night-memory-table.txt`. | One box read, 0 runs. |
| Does the skip's −500 MiB turn into frames when he moves? | Two of his own plays of ≥ 15 min at the same save, skip on then off (or exp 0379's S6N walking route, 2 × 2 arms), compared by flips/s per minute against mount reads per minute (F620's method). | 4 runs (~1.3 h) or two of his plays. |
| What do the learned windows pin outside the eager heaps? | One route arm with `BC5_DIRECT_LEARNED` pointed at an **empty** file, GTT max against a1; every learned fault it takes (a 14-s freeze each) counts the windows the title really needs. Beats P1 + L1 for the RAM question. | 1 arm (~19 min), low risk on a bench. |
| Was the e6 → e7 −7 % real? | The box read 0406 proposed: r6c's and r7m's `pinned … in N BOs`, `timing split` and `learned apply:` lines; then, if they differ, an ABBA pair of e6 and e7 with the skip on in both. | One box read; 4 arms if needed. |
| Is the mount's second page-cache copy costing frames now? | One walking pair with `BC5_MOUNT_DISK_CACHE` unset against set, mount reads per minute and flips/s per minute. | 2 arms. |
| Does lean (minus the wait) gain anything? | e9d/e9p/e9u as planned in 0401 "Series e9c", with `WAIT_LATE_PRODUCER_MS` removed from lean, on a walking route. | 6 arms. |
| Which mechanism did the maintainer mean? | Ask him, with the list in §B4b. | 0. |
| Did `FROM_PARAM=1` leave textures unloaded in the 17:55 play? | Not answerable now (no trace was on). Only matters if `FROM_PARAM=1` is wanted. | — |
| What is `AMM_PRT`'s page-table cost and is N1 worth it? | `BC5_DIRECT_AMM_PRT=0` against 1 on the standing bench: GTT max and any VM fault in the AMM window (F257's class would come back). | 2 arms. |

### F. What the next build should and should not contain

**Should** (each default off, one journal line, as the 0401 kit does):
- the plain zero skip (exp 0379/0388, the e7 `zsk` edit) **on in his shortcut** for one long play, as the first test
  — it is built, measured and the largest lever; the F403 risk is his call (3 in 19 arms, a successful reset each
  time in e8/e9, no machine-down);
- the memory line (`BC5_DIRECT_MEM_LINE`, e3+) kept on, so his plays are the measurement;
- L1 mode 1 (junk windows dropped, eager-covered chunks skipped) **with** the empty-learned-file arm run first, so
  its gain is a number before it is a switch;
- P1 (log only);
- N1 only because it is small and `AMM_PRT=1` is live; not for RAM.

**Should not:**
- `FROM_PARAM=1`, nor the AMM scatter built for it, unless he wants the console's budget for its own sake; neither
  is a RAM lever;
- Z2's redesign before the plain skip's F403 link is characterised (e9z1 already breaks the "canary take-back"
  story);
- R1 (≤ 0.35 GiB for memory.cpp surgery);
- the late-producer wait (2 of 5 crashes, B1);
- any A/B of memory on the standing route: the route must walk, or the measure must be his play.

### G. What would bring our memory implementation closest to the PS5's (added 2026-11-06 on the maintainer's question)

**Status of this section: written from four finished readers (I/O path, param.json census, disk-vs-RAM, unified
memory); a fifth pass (a seven-clone survey with two-lens verification of every proposed change) is still running and
its result will be merged here, so the ordered list at the end is provisional.** The readers' full fact sheets, with
every file:line, are in the session notes folder (`0408-io-path-facts.md`, `0408-param-json-census.md`,
`0408-disk-vs-ram-facts.md`, `0408-unified-memory-facts.md`); this section keeps the citations that carry a
decision. Sources are public clones under `Downloads/bc5/refs/` (shadPS4 60c42b9, KytyPS5 4644c52, AnyPS5 27c88a8,
RPCSX e8ae148, obliteration 2a53d5c, KytyPlus 3eee96a, Mesa ab2374a, fpPS4 04cefd4, GPCS4 88480de), Epic's public UE
forum post on PS5 page-table sizes, and our own records. **Nothing below about the real console comes from Sony
material; every console statement that is not in a public source is marked *inferred*.** The maintainer's word for the
"old rebuild" was the shared CPU/GPU mapping (ADR 0006, exp 0017/0023), so that comes first.

#### G1. Shared CPU/GPU memory: what the console does, what we do, how far apart they are

*The console model, as the public emulators reconstruct it (PS4 inherited by PS5).*
- One physical pool, two kinds of memory. Direct memory is allocated by physical address and then mapped at a
  virtual address; flexible memory is mapped without a physical address (shadPS4 `kernel/memory.cpp:45,198,259,265,350`,
  `memory.h:67-90`). RPCSX backs the whole pool with one shm file whose offset is the physical address
  (`iodev/dmem.cpp:406, 71`); AnyPS5 uses a memfd (`DirectMemory.cpp:294, 381`). **That is exactly our memfd (P:24896,
  24958-24980).** That a unified GDDR6 pool sits behind it on the console: *inferred*.
- Protection carries separate CPU and GPU rights: `CPU_READ/WRITE/EXEC 0x1/0x2/0x4`, `GPU_READ 0x10`, `GPU_WRITE 0x20`,
  identical in shadPS4 (`kernel/memory.h:36-43`), KytyPS5 (`memory.cpp:57-62`), RPCSX (`vm.hpp:38-47`), obliteration
  (`legacy/src/vm/mod.rs:204-211`), AnyPS5 (`DirectMemory.cpp:208`) and our KytyPlus (P:20408-20411); changeable later
  by `Mprotect`/`Mtypeprotect` and the batched `MAP_OP_*` (shadPS4 `memory.cpp:398,430`; `memory.h:46-52`).
- **GPU visibility is decided by those bits at map or protect time.** RPCSX maps the GPU only when `prot >> 4 != 0`
  (`gpu/Device.cpp:586-588`), the GPU view's rights are `prot >> 4` (`:1027, :650`), and unmap is protect-to-0
  (`:1046-1050`); AnyPS5 records a GPU mapping only with a GPU bit (`DirectMemory.cpp:705, 982, 1058`); KytyPS5 and our
  KytyPlus decode the bits into `GpuAccessMode` (P:20413, 20456-20470) and count GPU page-table entries only for
  ranges with a GPU bit (P:20836).
- Memory types are a property of the physical allocation: `WB_ONION 0`, `WC_GARLIC 3`, `WB_GARLIC 10` (shadPS4
  `kernel/memory.h:24-28`; fpPS4 `ps4_map_mm.pas:330-332`); RPCSX keeps one dmem file per type and maps the GPU from
  it (`Device.cpp:326-341, 595-597, 1023-1025`). What Onion and Garlic are on silicon (coherent through the CPU caches
  against direct to DRAM) is *inferred*; the only in-clone text is the descriptor memory-type tables of GPCS4 and fpPS4
  (`GnmConstant.h:400-421`; `ps4_shader.pas:180-187`). So coherence is chosen twice there: per allocation and per
  descriptor.
- GPU VA == CPU VA in a 2^40 window: every emulator hands the guest address to the GPU unchanged (KytyPS5
  `memory.cpp:88-106`; RPCSX `Device.cpp:619-631`, F92). KytyPS5 also accepts an "extended" window at
  0x0800_0000_0000 of 512 GiB (`regionDefinitions.h:15-27`), where our KytyPlus has the stricter
  `GPU_ADDRESS_LIMIT 1<<40` (P:20430-20433) — our host drops GPU map calls for addresses ≥ 2^40 that KytyPS5 accepts.
  The 40-bit translation that makes the 0x80 alias harmless (F92/F110) is still in no public source.
- Page-table budget: `PAGE_TABLE_POOL_SIZE` 4 GiB at 2 MiB granularity, `GetPageTableStats` counts a range toward the
  GPU total only with a GPU bit (KytyPS5 `memory.cpp:66-69, 495-510, 2690-2712`; ours P:20415-20419, 20825-20850). Two
  page tables over the same pages: *inferred* from the API shape.
- Nothing in the API suggests residency or eviction: a direct mapping is physical memory by construction. The only
  "eviction" in any clone is AnyPS5's host-side import budget with LRU retirement (`GuestBufferMemory.cpp:1486-1500,
  174-188, 1590-1600`) — an emulator problem, not a console one. Zero on reuse: AnyPS5 `ZeroReusedPhysical`
  (`DirectMemory.cpp:308-316`); console *inferred*.
- Unmapped GPU pages: no public source. A PRT aperture ioctl exists (obliteration `DMEMGETPRT 0xc018800c`,
  `legacy/src/fs/ioctl.rs:139`, unimplemented). "Reads 0, writes dropped" (exp 0102, F257) is inferred from the
  title's behaviour.

*Ours, item by item.*

| Item | Console | Ours (file:line) | Distance |
|---|---|---|---|
| Backing | one physical pool, offset = physical address | one sealed direct memfd + one 1 TiB private memfd, offset = guest address (P:24896-24906, 24958-24980); `MAP_SHARED\|MAP_FIXED` views (ADR 0006) | **same** (RPCSX, AnyPS5 do this) |
| GPU VA | == CPU VA, 2^40 window | == CPU VA (D:865-884) plus the 0x80 alias of the same BOs (D:911-936; P:29473-29520) | same, plus the alias workaround |
| What is GPU-visible | mappings with a GPU bit | **every** Direct view that holds data, by name list (`direct_views_build` ignores the protection argument; eager names P:28776-28800, lazy P:28757), plus learned windows and hints; the bits are decoded (P:20456-20470) and counted (P:20836) but never read by the mapper | **the largest semantic gap**: we replace the console's one rule with three heuristics (names, learned windows, zero list) |
| GPU rights | R, R\|W per mapping | R\|W\|X everywhere (`map_shared` D:870-871; aliases D:922-923; userptrs D:756-760; F257) | gap, 0 RAM |
| Memory types | per allocation, Onion/Garlic | stored (P:20715-20720, 22503, 23615-23616), never reach the mapper; our only `MTYPE_UC` are the IB scratch slots and the code buffer (D:473-480, 1652) | gap, 0 RAM; RADV itself uses UC only for one-shot command buffers (`radv_amdgpu_bo.c:43-44`, `radv_amdgpu_cs.c:234-236`) |
| Residency | physical by construction | udmabuf pins at creation (Linux `udmabuf.c`, `memfd_pin_folios`); import unit 2 MiB chunks with data merged into BOs ≤ `udmabuf size_limit_mb` (P:28697-28708, 28989-29060); the BO list per CS must all be resident (D:1478-1495; P:28749-28755: −ENOMEM at 6.8 GiB) | the console has no BO list and no "import"; AnyPS5 imports 64 MiB chunks **refcounted per guest buffer** and frees them when the last buffer dies (`GuestBufferMemory.cpp:624-719`) |
| Release | `ReleaseDirectMemory` frees the physical pages (shadPS4 `memory.cpp:113, 360-371`) | views are unmapped at the next sync (P:29126-29134) but the BO and its pinned pages stay until merged away or device close (P:29179; D:670-680); nothing is punched (P:25011) | gap; measured small so far (exp 0288 Q2: 74-350 MiB released-but-kept over 29 min, RT off; a level change is unmeasured) |
| Zero on reuse | fresh allocation is zero (*inferred*; AnyPS5 does it) | the private file is zeroed on re-commit (exp 0023); the direct memfd is not zeroed on re-allocation | gap, 0 RAM |
| Unmapped pages | *inferred* reads 0 / writes dropped | one 2 MiB zero BO mapped R\|W\|X under every learned-window hole (P:29597-29640, 29715-29735; it stops being zero once written, F257); the AMM window as NULL PRT when `BC5_DIRECT_AMM_PRT=1` (D:886-895), which **is** in the launcher | gap in kind (a writable zero page is not a dropped write) and a GFX10 hazard (Mesa `ac_gpu_info.c:437-442`) |
| Fault handling | a GPU fault is a crash there (*inferred*) | a fault is a 14-s freeze and a learned window (F88); F339 says `noretry=-1` keeps retry faults on for GC 10.1.3 (TODO(verify)) — the two rows are not reconciled | first-touch faults are not a residency mechanism here either way |

*Answer to the maintainer's first question.* The shared mapping itself — one file, GPU VA = CPU VA, the GPU reading
the title's pages in place — **is** the console's model and every other open PS5 host's. What is not console-like is
how we decide *which* pages the GPU may see (names, learned windows, a zero list, all per title) and the fact that a
page once shown to the GPU is pinned for the run. The changes that close that gap are G6 items 1-4 below.

#### G2. param.json: what the firmware uses, what we honour

The patch's `systemContent.cpp` hunk (P:56941-56990) adds no param.json read, so our host reads exactly KytyPlus
f266548's keys: `titleId`, `contentId`, `contentVersion`/`appVersion`, `userDefinedParam1..4`,
`kernel.flexibleMemorySize` (276 MiB for the title, F194), `localizedParameters.defaultLanguage` and `<lang>.titleName`
(f266548 `src/loader/systemContent.cpp:164-217`). The census found 38 key paths in public parsers and documents
(KytyPS5, AnyPS5, pcsx5, the two public gists, Epic's forum post; psdevwiki itself answered 403, so only its search
snippets were used). Of the 29 we do not read, these have a runtime consumer somewhere public:

| Key | Firmware use (P public, I inferred) | Source | Change, switch | Risk | Effort |
|---|---|---|---|---|---|
| `kernel.cpuPageTableSize`, `kernel.gpuPageTableSize`, `amm.pagetableMemorySizeInMib` | page-table memory per side, 64 MiB included, more comes off the ~12.5 GiB budget; feeds `sceKernelGetPageTableStats` (P: KytyPS5 09753bf `systemContent.cpp:+183-190`, `memory.cpp:+70-81, +1005-1019, +2668-2673`; Epic: UE raises Cpu/GpuPageTableSize 64 → 96 MB; that pubtools writes it here is I) | KytyPS5, Epic | exp 0401's `KYTY_BC5_MEMORY_FROM_PARAM` ports the budget (B4a: ~120 MiB, and the AMM fatal). **Split a stats-only switch** `KYTY_BC5_PAGE_TABLE_STATS_FROM_PARAM` that changes only `KernelGetPageTableStats` (P:23137-23160, today a fixed 2048 entries per side; AnyPS5 also hard-codes 8192) | high for the total (F394: no start at 12,288 MiB; F353: the title reserves 12,162 of 13,824); low for stats-only | M / S |
| `attribute` (bit 29 = HDR supported) | `dynamicRange` in the VideoOut status (P: KytyPS5 `systemContent.cpp:167-168`, `videoOut.cpp:1864-1871`; gist) | KytyPS5, KytyPlus HEAD | parse at `:171`; use in `VideoOutGetResolutionStatus` (base `videoOut.cpp:1664` answers 1 always). `KYTY_BC5_PARAM_ATTRIBUTE` | low | S |
| `attribute3` (bit 6 = 120 Hz, bits 18-20 VRR, bit 22 PS5 Pro, bit 2 resolution detection per KytyPS5) | 120 Hz output mode allowed; `resolution` field (P: KytyPS5 `videoOut.cpp:1862-1868`; AnyPS5 `Output.cpp:275` refuses mode 15 without bit 6) | KytyPS5, AnyPS5 | parse; gate `VideoOutConfigureOutput` mode 15 and `status->resolution`. `KYTY_BC5_PARAM_ATTRIBUTE3` | low-medium (a 120 Hz path is untested here) | S |
| `downloadDataSize` | the `/download0` quota for `sceAppContentDownloadDataGetAvailableSpaceKb`; 0 = no area (P: AnyPS5 `ParamJsonParser.cpp`, `AppMetadata.cpp:58-66`, `libSceAppContent/Export.cpp:106-115`) | AnyPS5 | answer min(host free, quota) instead of host free space (f266548 `libAppContent.cpp:139-145`). `KYTY_BC5_DOWNLOAD_QUOTA_FROM_PARAM` | low | S |
| `kernel.flexibleMemorySize` | read already; our no-key default is 1 GiB (P:20419) against 448 MiB upstream (KytyPS5 0a14091; AnyPS5 `DirectMemory/Export.cpp:40-47`); the module-segment charge to flexible (0a14091) was left out by exp 0401 | KytyPS5, AnyPS5 | lower the no-key default; the charge is a runtimeLinker change | low / medium | S / M |
| `requiredSystemSoftwareVersion`, `sdkVersion` | minimum firmware; SDK version, encoding `0x0700000000000000` (P gist) | KytyPS5 launcher `:561-584`; pcsx5 | journal only: the host takes the SDK version from the ELF already (P:35224), as AnyPS5 does | — | S |
| `applicationCategoryType`, `addcont.serviceIdForSharing[]`, `localizedParameters` choice by console language | application vs addcont; DLC service labels; display title | KytyPS5 `additionalContent.cpp:87-89`; pcsx5 | none for the second title; port with addcont scanning if ever | — | S |

The rest (`masterVersion`, `conceptId`, `applicationDrmType`, `contentBadgeType`, `attribute2`, `attribute4`,
`ageLevel.*`, `pubtools.*`, `versionFileUri`, `disc[]`, `asa.*`, `sign`) has no runtime consumer in any public
emulator; pcsx5 parses and stores them unused. `targetId` and `deviceOrientation` have no public parser or document.

*Answer to the maintainer's second question.* He is right that we expose almost nothing: 9 of 38. But only three of the
unread keys touch memory, and they only size the budget, which is not a RAM lever on this box (B4a). The ones worth
honouring for fidelity are `attribute`/`attribute3` (what the title is told about HDR and 120 Hz) and
`downloadDataSize`, each a small switch.

#### G3. The I/O path: three page-cache copies where the console (inferred) has none

Between the NVMe and the title's memory our APR path holds **three resting page-cache copies and four user buffers**
(the reader's count, each with its citation): (1) the kernel's page cache of the image file, or of the disk cache's
`.data` file (`tools/bc5-mount/src/io.rs:144, 185-187`; `diskcache.rs:160`; no `O_DIRECT` anywhere in bc5-mount);
(2) the `payload` Vec of compressed bytes (`io.rs:42-45`); (3) the decoded block, kept in the 32 MiB block cache
(`pkg/inner.rs:26, 90-91`); (4) the FUSE reply buffer (`fuse.rs:298-303`); (5) **the kernel's page cache of the mounted
file** — open replies `FOPEN_KEEP_CACHE` (`fuse.rs:269`), no `direct_io` on main; (6) the emulator's staging: the
read-ahead reader's `ra_data` (P:39408-39438) or `ReadHostFileToGuest`'s thread-local 4 MiB buffer (KytyPlus
`libAmpr.cpp:1445-1453`, unchanged by the patch); (7) the `memcpy` into guest memory (P:39182; `libAmpr.cpp:1458`),
whose pages are shmem and pinned once imported. `sceKernelRead/pread` skip step 6 (P:15026, 15162). No clone opens
title files with `O_DIRECT` or fadvise for APR (KytyPlus has the hook, `sysLinuxFileIO.cpp:61-80`, unused); AnyPS5 reads
straight into guest memory on Linux (`Apr.cpp:181`). That the console decodes Kraken in hardware and DMAs into the
destination pages with no OS file cache is *inferred* (nothing in any clone says it; the command ABI — destination VA,
offset, size, gather/scatter, KytyPS5 `libAmpr.cpp:654-660, 2075-2147` — is consistent with it).

What has been measured: repeats are 67-88 % of what the mount serves (exp 0381 RR3/RR4), the title asks only
1.04-1.16× what the mount serves, so the mounted-file page cache (copy 5) spares at most 4-14 %; 76-85 % of repeats
are 16-256 s old, i.e. plain eviction from a ~900 MiB file LRU (F814); the DROP_BACKING + small-readahead bundle cut
NVMe bytes 28-37 % but lost 4-6 % of flips (RR4); a 64 GiB disk cache removed 91-96 % of decode time with no flip
gain (RR5); **the `BC5_MOUNT_DIRECT_IO=1` arm (exp 0381 build 5249deee, `fuse.rs:299-303`) was never run.**

#### G4. Eager heap import and learned windows: the console has one rule, we have three heuristics

The console commits GPU-visible memory at map time, by the GPU bits (G1); there is no eager/lazy distinction and no
learning, because a GPU access outside a GPU-mapped page is a fault, not a lesson. Our eager list (10,047 MiB, 90 % of
the pin, F353), lazy list (−242 MiB, F394), 110 learned windows (3.9 GB asked at every start, mostly inside the eager
heaps, F353/F402) and the zero list (−500 MiB, §A) are all stand-ins for "import iff GPU bit", each tuned to one
title. The closest generic on-demand scheme on this Linux stack:
- *fault-driven residency* (shadPS4's `FaultManager` over a BDA table it controls) is not available to us: we run the
  title's own shaders, and the box cannot fault-and-retry on graphics queues (F88; F339's `noretry` note is the one
  open doubt);
- *sparse binding* (RADV's `AMDGPU_VA_OP_REPLACE` over a null BO, `radv_amdgpu_bo.c:144-181, 213-245`) gives a
  **universal "unbacked reads 0" rule** without per-title lists, which is what our scratch BO and PRT window
  approximate by hand; it does not make pages resident on demand;
- *import by the title's GPU bits at map time* (RPCSX `Device.cpp:586-588`; AnyPS5 `DirectMemory.cpp:705`) is the
  console's own rule and needs no per-title data: GPU_WRITE views imported in full when mapped, GPU_READ-only views
  by `SEEK_DATA`, CPU-only views never. 0407's P1 census is the measurement that says how much of today's import that
  rule would keep; nothing says yet whether the second title maps its CPU heaps with GPU bits.

*Answer to the maintainer's third and fourth questions.* Importing a heap in full at map time is what the console
does for a GPU-mapped heap — the difference is only that there the untouched pages cost nothing extra and here udmabuf
materialises them (F394's 3.7 GB of zero). The universal replacement for the learned windows is the GPU-bit rule plus
a null-BO sparse backing for everything else; the learned file then becomes a diagnostic of titles that read GPU-wise
through CPU-only mappings (which the console would also fault on).

#### G5. Disk instead of RAM: what can move, what cannot

Under udmabuf nothing the GPU has seen can be read on demand: the title's pinned 11.2-11.4 GB (F353) is the elephant
and is not a candidate. What is left, with the reader's numbers:

| Candidate | RAM today | Change | Gain / cost | Console equivalent |
|---|---|---|---|---|
| The journal and play log through the page cache | ~200 MB per 10 min written (exp 0330); the normal build's write-through cost 309 MiB swapped out and 45,700 major faults per 5 min against 30 MiB / 3,000 lean (F353) | carry exp 0330's `BC5_DIRECT_JOURNAL_DONTNEED` (fadvise after each 8 MiB; arm B: pswpout 80,227 → 2,954, flips 36.8 → 36.4) into the patch (~30 lines); `JOURNAL_QUIET` already cut 385 → 24 MB a run | swap traffic and major faults; 0 flips | none |
| A fresher, larger zero list and shared canary slices | the list skips 583 MiB in play (F631), 1.9 GB on the bench (F541); canaries 104 MiB for 52 runs (F631) | a SCAN play over every eager name and the AMM pool (F625 item 1: ~1.5 GB + 3.1 GB in small pages, unmeasured); one canary slice per heap (F632) → ~4 MiB | 0.6-1.9 GB pinned; cost = canary hits (one per 2.4 min, F631) and the F403 association | none: the console allocates what the title asks and nothing is "imported" |
| The mount's page-cache copies (G3) | whatever is left after the pin; F394: 9-11.5 M file pages reclaimed per 10 min | `BC5_MOUNT_DIRECT_IO=1` + `CACHE_MIB=512` (one bounded copy), `DROP_BACKING`, FADV_DONTNEED on the `.data` file (~20 lines) | the only lever on the F505/F689 re-read thrash; built, unrun | none (inferred) |
| The on-disk decoded cache (8 GiB, no eviction, full since 10-25, 196 GiB decoded) | ~6 MiB of map in RAM, plus its `.data` pages in the page cache | eviction (~100-200 lines) or a larger private cache, or the opposite arm (no disk cache: compressed reads move fewer NVMe bytes) | direction unknown (RR5: decode time is not the limit) | none |
| KytyPlus's staging buffers and the DMA snapshot ring | 96 + 16 + 16 + 16 MiB (P:4850-4862, F47); 64 MiB ring (D:279-296) | `KYTY_BC5_CACHE_MIB=48,16,16,16`; a 32 MiB ring if `dma_snapshot_overflow` (P:34448-34452) stays 0 | ~80 MiB, env/constant | none (host presentation) |
| bc5-mount's RSS | 695-840 MiB, ~600 of it unattributed (exp 0288 README:146-148) | heap profile first; pooled per-read Vecs, 4 workers | unknown until profiled | none |
| ASTRO BOT's PFSC block cache | 1,024 MiB (`pfsc.rs:40`; ~850 real, exp 0121) | `BC5_MOUNT_CACHE_MIB=256` for that title, or a PFSC disk cache (the pkg DiskCache is generic) | not the starved title | none |

Not candidates, with the reason: a "JIT cache" — KytyPlus has no recompiler (`src/loader/jit.h` holds thunks only;
segments are read straight into the mapped segment, `elf.cpp:242-282`), the only per-start work is the TLS pattern scan
and relocation (`runtimeLinker.cpp:1406-1449, 1533-1551`, unmeasured), and a relocated copy of the title's code on disk
is material we must never keep; BVH and other GPU-derived data — rebuilt per frame by the title's own dispatches inside
its heaps (F370, F381), the console does the same (inferred); APR read-ahead data — ≤ 32 MiB, freed at the worker's
turn, no decoded asset kept beyond what the title asked; the eager heaps' 4 KiB zero holes (~1 GB beyond the 2 MiB
list, F394) — unreachable without a 512× BO count.

*Answer to the maintainer's fifth question.* Almost nothing we hold in RAM is a cache of something regenerable: the RAM
is the title's own memory, pinned. The disk already holds the decoded blocks (8 GiB), the zero list and the learned
file. What is worth doing on disk is bounding the page-cache copies of the mount (G3) and the journal's writes; a code
or BVH cache would gain nothing and the first is off limits.

#### G6. The ordered change list (provisional until the verification pass is merged)

Order by: console fidelity first where the RAM effect is neutral, then RAM per unit of risk; the three items that
need a measurement before code come with that measurement.

| # | Change | Console does (source / inferred) | We do | RAM | Frame | Risk on gfx1013 | Effort | 0407 |
|---|---|---|---|---|---|---|---|---|
| 1 | **Protection census** (log per view: name, CPU/GPU bits as given, before `ALL_RW` widens them, eager/lazy/data, bytes imported) | the bits are the rule (G1) | bits decoded, never read (P:20456-20470) | 0 | 0 | none | S | = P1, agreed; it gates 2-3 |
| 2 | **Import by the title's GPU bits**: pass the protection into `direct_views_build`; GPU_WRITE views eager, GPU_READ-only by `SEEK_DATA`, no-GPU-bit views not imported; re-sync on `SetProtection` (the generation already bumps, P:20710); the name lists become an override, the learned windows a safety net with a journal line | RPCSX `Device.cpp:586-588`; AnyPS5 `DirectMemory.cpp:705` | name lists (P:28757, 28776-28800) | what the census says the CPU-only heaps cost (the lazy list's −242 MiB is the lower bound) | fewer BOs in the full list (F125 scale) | a title that reads GPU-wise through a CPU-only mapping faults — the console would too; the learned window catches it once | S after 1 | not proposed; this is the universal mechanism the maintainer asked for |
| 3 | **Per-mapping GPU rights** (R or R\|W from the bits; X only for the code alias) | RPCSX `prot >> 4` (`Device.cpp:1027`) | R\|W\|X everywhere (D:870-871) | 0 | 0 | writes through a GPU_READ-only mapping would fault; no known case (F257's clears hit unmapped blocks) | S | not proposed |
| 4 | **Null-BO sparse backing for everything unbacked** (the AMM window and the learned-window holes) instead of NULL PRT and the writable zero BO; `AMDGPU_VA_OP_REPLACE` already handles mappings inside (D:99-105) | reads 0 / writes dropped (*inferred*, F257); RADV's `bind_low_null_prt` is the Linux form | PRT window (D:886-895, live in the launcher) + a writable 2 MiB zero BO (P:29604-29616) | 0 (VA only) | 0 | removes a GFX10 SMEM hang hazard (Mesa `ac_gpu_info.c:437-442`); a real missing import then reads 0 instead of faulting, so keep the learned import first; what a write to a non-writable page does with retry off is TODO(verify), its own arm | S | = N1, agreed, extended to the holes |
| 5 | **Zero skip on in his shortcut, then a fresher list with shared canary slices** (G5) | nothing to import there (the console pays nothing for untouched pages) | off by his choice | −500 MiB measured now; 0.6-1.9 GB with the fuller list | 0 standing; the walking gain is unmeasured (§E) | F403: 3 in 19 arms with it | 0 / S | 0407's Z2 redesigns it before the plain form's F403 link is characterised: disagree on order |
| 6 | **Journal `DONTNEED`** carried into the patch (G5) | no OS page cache in the path (*inferred*) | write-through journal | swap traffic | 0 | none (one arm clean) | S | not considered |
| 7 | **Learned-window trim, mode 1** after an empty-learned-file arm has measured the windows' real cost (§E) | no learning on the console | 110 windows × 96 MiB (P:29546-29548), applied from the submit path (P:33845) | ≤ 0.7 GB (unmeasured) | the 633-ms `learned_apply` stalls (exp 0288) | a needed chunk faults once (14 s) | S | = L1, agreed on the change, not on doing it before the measurement |
| 8 | **Release on free**: refcount per chunk (`SharedBo::maps`, D:879); when a guest release leaves a BO with no view, `free_shared` after the drain the merge already does; punch the memfd range then | `ReleaseDirectMemory` frees the pages (shadPS4 `memory.cpp:360-371`); AnyPS5 frees chunks on the last buffer | nothing freed (P:25011, 29179) | ≤ 0.35 GiB measured (exp 0288 Q2); a level change unmeasured | 0 | a stale GPU mapping after the free is a fault: unmap first; pin/unpin churn | M | = R1; agreed, ranked lower until a level change is measured |
| 9 | **Zero on reuse** of direct memory (`memset` in `AllocateDirectMemory` when the range was used before; with 8, a punch instead) | fresh allocation is zero (*inferred*; AnyPS5 `DirectMemory.cpp:308-316`) | private file only (exp 0023) | 0 | a memset per allocation | none | S | not considered |
| 10 | **Mount page-cache bounding**: run the built `DIRECT_IO` + `CACHE_MIB=512` arm, `DONTNEED` on the `.data` file; then decide on `DROP_BACKING` | no OS file cache (*inferred*) | three copies (G3) | up to the whole page-cache residue | the only lever on F620/F689's re-reads; RR4 says the bundle without `DIRECT_IO` costs 4-6 % | medium (a repeat the backing copy caught hits the NVMe) | 0 (built) | 0407 names it, defers it to a mount experiment: agreed that it is separate, disagree that it waits |
| 11 | **param.json: stats-only page-table switch, `attribute`/`attribute3`, `downloadDataSize`** (G2) | the firmware reads them (P) | 9 of 38 keys read | 0 | 0 | low | S each | not considered |
| 12 | **Memory types to the mapper** (`AMDGPU_VM_MTYPE_UC`/NC for WC_GARLIC/UC areas; read which types the titles use from the journal first) | per-allocation Onion/Garlic (*inferred* semantics) | all default MTYPE | 0 | unknown either way (GL2 bypass can lose fps or remove F172-class staleness) | low (a VM flag) | S + M measurement | not considered |
| 13 | **Accept the extended window** (addresses ≥ 2^40 up to KytyPS5's 0x0800_0000_0000 + 512 GiB) in `IsGpuAddressRange` (P:20430-20433) | KytyPS5 `regionDefinitions.h:15-27` | dropped | 0 | 0 | none known | XS | not considered |
| — | Not adopted, agreeing with 0407: userptr (F24), KFD SVM, copying into device buffers, unpinned udmabuf. Not adopted, beyond 0407: a GTT-budgeted LRU of imports (AnyPS5's) — a re-import miss is a 14-s fault here; the 4 KiB zero holes; a code cache. |

*Where this list disagrees with 0407's ranked plan:* 0407 ranks by RAM gain over risk and puts L1 first, R1 second
and Z2 fourth; none of its five changes makes the GPU-visibility rule console-like, which is the maintainer's
question. Here the GPU-bit rule (1-3) comes first because it replaces three per-title heuristics with the console's
one rule at zero RAM risk, and the measured lever (the plain skip) comes before any redesign of it. On N1, L1, P1 and
R1 the two lists agree on the change and differ only in order.

## Verdict

**Review done; nothing tested.** Of the reviewed claims, the file:line citations, the "host CPU on the render thread"
fact, the catcher drops (0406 items 1–3, 9), the crash attribution to the late-producer wait, and the AMM
fragmentation reading hold. "The e6 → e7 drop is noise" is unresolved, not shown. "`FROM_PARAM` made play smooth and
its removal brought the choking back" is wrong: a 155-s play against 11–35-minute plays, with a ~120 MiB measured
gain. The four old mechanisms have not changed since 10-21. The pressure he feels is the eager import climbing, with
RT on, to the 13 GiB GTT ceiling in long moving plays, made ~500 MiB worse by running without the zero skip, in a
heavier part of the game than on 10-21. The next build is mostly a test of what already exists, with one new
measurement (the empty learned file) ahead of any new memory code.
