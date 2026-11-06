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

## Verdict

**Review done; nothing tested.** Of the reviewed claims, the file:line citations, the "host CPU on the render thread"
fact, the catcher drops (0406 items 1–3, 9), the crash attribution to the late-producer wait, and the AMM
fragmentation reading hold. "The e6 → e7 drop is noise" is unresolved, not shown. "`FROM_PARAM` made play smooth and
its removal brought the choking back" is wrong: a 155-s play against 11–35-minute plays, with a ~120 MiB measured
gain. The four old mechanisms have not changed since 10-21. The pressure he feels is the eager import climbing, with
RT on, to the 13 GiB GTT ceiling in long moving plays, made ~500 MiB worse by running without the zero skip, in a
heavier part of the game than on 10-21. The next build is mostly a test of what already exists, with one new
measurement (the empty learned file) ahead of any new memory code.
