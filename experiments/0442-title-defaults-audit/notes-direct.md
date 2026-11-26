# Audit: the 18 direct-path rows of kTitleDefaults (TITLE2)

Worktree `~\Downloads\bc5\wt0442`, read-only. "patch N" = line N of
`backend/kytyplus-patches/0001-bc5-lle-agc.patch`. Most reads are in `+++ b/src/libs/bc5LleAgc.cpp`
(written below as "bc5LleAgc.cpp"). Backend = `backend/src/direct.cpp`.
Third title = TITLE3 (`experiments/0439-third-title/README.md:7`).

## Two general findings about the table first

- **Two rows are forced, so NAME=0 cannot turn them off.** `kTitleForced = {BC5_DIRECT_LAZY_RELEASE, BC5_GUARD_SPLIT}`
  (patch 6255). `Apply()` *unsets* both for every title (patch 6310-6312). `ApplyTitle` then sets them with overwrite=1
  (patch 6271). Result: on TITLE2 they are always on, and an environment value cannot change that. Only
  `KYTY_BC5_TITLE_DEFAULTS=0` (patch 6321-6322) turns them off, and so does `KYTY_BC5_DIAG_UNFORCE`, which applies to
  kFixes/kDefaults only. On the first title and the third title they are always off and cannot be turned on from the
  environment. The task's premise ("NAME=0 turns one off") is wrong for these two rows.
- **"=0" does not mean off for three rows:**
  - `BC5_DIRECT_SHADOW_LABELS` tests presence only (direct.cpp:588), so "=0" turns it on.
  - `BC5_DIRECT_INDIRECT_DRAWS=0` lets DRAW_INDIRECT through (the same as "=1") and turns on the given-up-wait drop
    (patch 53924-53925, 54086).
  - `BC5_DIRECT_SKIP_PGM=0` is the row's own value: it parses to the set {0} (patch 54142 with the pgm_list lambda at
    53982-53994).
  - The rest use `bc5::env_on` (unset, empty and "0" are off; patch 16267, `backend/include/bc5/env_flag.hpp:8`) or
    parse "0" as off.
- `experiments/0419-switch-cleanup/switch-inventory.tsv` says "presence only, =0 is ON" for MEC_INDIRECT, GPU_CHECK,
  DMA_SYNC, REMEMBER_UNMAPPED, AMM_PRT and ALIASES. That is out of date: the patch now reads all six with `bc5::env_on`,
  as its "exp 0419: =0 is off" comments say. The launcher comment `tools/scripts/launchers/play-pkg.sh:123`
  ("PRT on whenever set at all") is out of date for the same reason.
- None of the 18 words is in kFixes, kDefaults or kSoft (grep over patch lines below 6400: only the title rows
  6157-6174 and kTitleForced 6255).

---

## 1. BC5_DIRECT_LAZY_RELEASE = "30,eager"
1. **Read:** bc5LleAgc.cpp, patch 41313 (`Lzr0401::parse(getenv(...))`); parser at patch 40966-41008. Not in backend/.
   - **On:** in `direct_sync_one` (`lzr_pass`, patch 41341ff) the direct memfd's chunks that have been under no view
     for 30 s are found, and once per pass period (a quarter of the idle time, 1-15 s, patch 41013-41016) they are cut
     out of their BOs: the kept runs are re-imported, the old BO is retired, and the mappings are rebuilt. "eager" lets
     chunks of eager heaps be cut too.
   - The cut stands only if every ring is idle (comment, patch 41290-41300).
   - **Off / unset (code default):** one journal line, then a return (patch 41355-41358).
   - **Forced for TITLE2 and unset for every other title** (see the general findings).
2. **Finding:** no F row of its own.
   - HANDOFF F843 (docs/HANDOFF.md:826): "...`BC5_DIRECT_LAZY_RELEASE=30,eager` with `BC5_GUARD_SPLIT=1` forced for the
     second title". Also docs/HANDOFF.md:1014.
   - Introduced in exp 0401 series e7 (`experiments/0401-*`, tool mklzr0401.py) and made live in exp 0412
     (memory guardian). Audit row B15: `experiments/0413-np-session-v2-shared/audit-unintegrated.md:66`, "16-31 cuts a
     run, no fault, 0.1-0.2 GiB; fast2 cut 1,548 MiB, 96 % came back".
3. **The first title / third title:** no run found with it on.
   - `experiments/0419-switch-cleanup/owners-verdicts.md:51` and `candidate-G-plan.md:42` both still owe "one arm
     without on both titles".
   - The first title cannot get it in this patch (it is unset at start).
   - No negative first-title result is recorded.
4. **Every-title paths:** yes, if it were on. It changes memory mapping (BO split/free, mapping rebuild, aliases
   re-mapped) on the sync path every title uses, and adds a wait_idle check. It acts on direct memory only
   (`S.kind == 0`).
5. **Title-specific?** The mechanism holds no title data.
   - The log text says chunks are cut only when "not forced by a hint or learned window" (patch 41349).
   - The "zero list" heap names (RenderGpuWcLarge, CommitIABufferAllocator) are compiled off
     (`lzr_zero_skip` returns false, patch 41317-41319).
   - It is a memory-use optimisation, not a correctness fix.

## 2. BC5_GUARD_SPLIT = "1"
1. **Read:** bc5LleAgc.cpp, patch 44350 (`guard0412_split()`, `bc5::env_on`). Used at patch 41410 and 44356.
   - **On:**
     - the lazy release may split BOs that carry aliases (`splits = !aliases_on || guard0412_split()`, patch 41410);
     - after a sync with cuts, the aliases are mapped again at once (`aliases_apply(true)`, patch 44355-44359).
   - **Off (default unset):** with BC5_DIRECT_ALIASES on, aliased BOs are not split.
   - Forced on TITLE2, unset elsewhere (patch 6255/6310).
2. **Finding:** no F row of its own (F843, docs/HANDOFF.md:826). Exp 0412, tag g412c. Same audit row B15.
3. **The first title / third title:** not found. It only acts together with LAZY_RELEASE
   (`experiments/0419-switch-cleanup/switch-inventory.tsv` note).
4. **Every-title paths:** only through LAZY_RELEASE (mapping changes). By itself it does nothing.
5. **Title-specific?** No data. It is a helper of LAZY_RELEASE and only matters with ALIASES on.

## 3. BC5_GUARD_LEARN_LOG = "2"
1. **Read:** bc5LleAgc.cpp, patch 40132 (`mr412::env_digit(..., 2)`; unset or invalid = 0).
   - Its only uses are patch 43491 and 43512, both inside `alias_learn()`, which is marked
     `[[maybe_unused]] ... // exp 0419: not called` (patch 43489).
   - The "would learn" journal (`mr412_would_learn`, patch 43572-43573) runs always: "BC5_GUARD_LEARN_LOG no longer
     decides".
   - **The row is inert in this patch:** on, off or unset, no behaviour changes.
2. **Finding:**
   - HANDOFF F819 (docs/HANDOFF.md:802): "The learned-windows file held three different things under one name, and none
     was needed on the scripted route..."
   - HANDOFF F820 (docs/HANDOFF.md:803): "The learned windows are gone from the second title's three shared launchers
     since 2026-11-13..."
   - Introduced in exp 0412 (tag mr412).
3. **The first title / third title:** `experiments/0412-memory-guardian/README.md:2793`: "the first title's launcher names no learned
   file". No first title or third-title run with it set was found. No negative result.
4. **Every-title paths:** none (dead read).
5. **Title-specific?** It belonged to the learned-windows/alias-learning machinery (learned title data). Today it is a
   diagnosis switch with no effect. It is a candidate for deletion from the table.

## 4. BC5_DIRECT_MEC_INDIRECT = "1" (F91)
1. **Read:** bc5LleAgc.cpp, patch 53965 (`bc5::env_on`). Used at 54189 and 54238.
   - **Off (default):** a compute-form DISPATCH_INDIRECT (op 0x16, len 4) in an acb that is submitted on the **GFX ring**
     is dropped (patch 54189-54192).
   - **On:** such dispatches are counted per high address dword, and the IB is rebuilt with GFX-form dispatches
     (`mec_expand_ib`, patch 54238). The backend uses `mec_indirect_base` and `PFP_SYNC_ME` (direct.cpp:1365-1379).
2. **Finding:** HANDOFF F91 (docs/HANDOFF.md:185): "The second title's compute IBs' indirect dispatches run on the GFX
   ring, and the title gets past the moment that used to fault in two runs of three."
   - Source: `experiments/0039-compute-indirect-dispatch`. The off-by-default history is in F90 (docs/HANDOFF.md:184,
     exp 0038).
3. **The first title / third title:** no run with it on was found.
   - F90 (docs/HANDOFF.md:184) and `experiments/0038-pkg-title-stability/README.md:41`: "the first title on the safe build
     (run 150, 420 s): 56.5 fps". That safe build had it off.
   - ADR 0009 (`docs/decisions/0009-compute-ring.md:5`): the first title's launcher kept only BC5_DIRECT_RINGS=1, not this word.
   - No negative first-title result.
4. **Every-title paths:** yes, but only for acb compute-form indirect dispatches that land on the GFX ring.
   - It changes GPU submission (IB rebuild versus drop).
   - With way 2 (ACB_RINGS=4 in kSoft for every title, F850) acbs go to compute rings, so the branch matters only when
     an acb falls back to the GFX ring.
   - Note: kSoft has a separate `BC5_DIRECT_ACB_MEC_INDIRECT` for the compute rings (CLAUDE.md:74).
5. **Title-specific?** No addresses or lists. It is a generic fix (run, rather than drop, a packet class).

## 5. BC5_DIRECT_GPU_CHECK = "1" (F106)
1. **Read:** bc5LleAgc.cpp, patch 54000 (`bc5::env_on`), which sets `opt.gpu_check_indirect = true` (patch 54001).
   Backend use: direct.cpp:1435-1445 (`indirect_check::apply`); the PFP path is skipped when it is set
   (direct.cpp:1375).
   - **On:** before every DISPATCH_INDIRECT the backend inserts `WRITE_DATA` + `COND_WRITE`s + `PFP_SYNC_ME` +
     `COND_EXEC`, so the CP skips absurd group counts at run time. The host's stale submit-time check then no longer
     drops dispatches with a known base.
   - **Off (default):** only the host's submit-time sanity check (drops on stale values).
2. **Finding:** HANDOFF F106 (docs/HANDOFF.md:200): "Indirect dispatch arguments can be checked by the CP when it runs
   the dispatch, and with that the second title builds its trees' leaf lists..." Source:
   `experiments/0052-gpu-checked-indirect`.
3. **The first title / third title:** not found. Inventory: "the first title with it: not checked by me". No negative result.
4. **Every-title paths:** yes. Every indirect dispatch of every buffer gets extra packets, comp and GFX alike (no
   `!comp` at direct.cpp:1435). This changes GPU submission and adds small per-dispatch GPU timing.
5. **Title-specific?** Generic. The draw limits (2^20 vertices, 64 instances, patch 53938-53939) were sized on the
   second title's largest draw (94,322 vertices, one instance), so they are a guard with values tuned to one title.

## 6. BC5_DIRECT_DMA_SYNC = "1" (F107)
1. **Read:** bc5LleAgc.cpp, patch 53881 (`bc5::env_on`), which sets `opt.dma_sync_before_dispatch` (patch 53882).
   Backend: direct.cpp:1401 (`if (opt.dma_sync_before_dispatch && !comp)`).
   - **On:** a CP DMA wait before the first dispatch after an unsynced DMA_DATA, on GFX-ring jobs only.
   - **Off (default):** none.
2. **Finding:** HANDOFF F107 (docs/HANDOFF.md:201): "The second title's tree refit runs: it also needed a wait for the
   CP DMA copy of its tree." Source: `experiments/0053-pkg-title-refit-runs`; the switch itself is from exp 0050.
3. **The first title / third title:**
   - F894 (docs/HANDOFF.md:877): the third title's ~25 s start-up stall is "the same race" as F107. "its fix,
     `BC5_DIRECT_DMA_SYNC`, is a TITLE2 default only and acts on the GFX ring only, so it was off in every
     third-title run."
   - The planned test (Q41, docs/HANDOFF.md:926; `experiments/0439-third-title/k439/t3one.sh:11-21`, variant "fixes"
     with `BC5_DIRECT_DMA_SYNC=1`; README:978) is **Open**. No result is recorded (README ends "(more to come)").
   - The first title: not found. No negative result for either title.
4. **Every-title paths:** yes, on GFX-ring submissions with unsynced DMA_DATA (GPU submission and timing: an added
   wait). F894 argues that the same wait is also needed on the compute rings (candidate D, `BC5_0439_DMA_SYNC_MEC`,
   private).
5. **Title-specific?** No data. It is a generic ordering fix, and F894 gives evidence that a second title needs it.

## 7. BC5_DIRECT_REMEMBER_UNMAPPED = "1" (F163)
1. **Read:** bc5LleAgc.cpp, patch 53681 (`bc5::env_on`); logic at patch 53682-53870.
   - **On:** a light IB (no draw, dispatch or nested IB) whose only unmapped operands lie in pages that a forced sync
     left unmapped less than 2 s ago does not force another full sync walk. Its packet is dropped either way.
   - **Off (default):** every such IB forces the full `/proc` sync walk.
2. **Finding:** HANDOFF F163 (docs/HANDOFF.md:257): "The second title's intro runs its whole renderer behind the logo.
   Its 62 ms frame holds 9 ms of host sync..." It gives 16.9 -> 18.2-18.6 fps. Source: experiment 0103.
3. **The first title / third title:**
   - The code comment (patch 53679-53680) says the second title's "(and the first title's) 84-dword DCB after every flip has
     one such operand".
   - `experiments/0103-pkg-title-intro-frame-time/README.md:49` says "the first title does not pay this cost (sync 0.1 ms a
     frame in its 09:21 run)". The two disagree.
   - Exp 0108 (`experiments/0108-pkg-fixes-soak-and-t1-check/README.md:4-38`) checked the first title with the *binary* only;
     the knob was set only for the second title (run400.sh:11).
   - No first-title run with it on, and no negative result.
4. **Every-title paths:** yes. It changes when the host's mapping sync runs (timing and the freshness of mappings) on
   the submit path. The dropped packet is the same either way.
5. **Title-specific?** No data. Pages remembered for 2 s are a run-time cache, not a learned file. It is a speed fix.

## 8. KYTY_BC5_APR_PARALLEL = "8" (F166)
1. **Read:** `+++ b/src/libs/libAmpr.cpp`, patch 59928 (`strtol`; unset or <2 = 0, off; capped at 32).
   - **On:** runs of consecutive ReadFile commands in one APR command buffer, with non-overlapping destinations, run on
     n threads (patch 59936-59955).
   - **Off (default):** one read at a time.
2. **Finding:** HANDOFF F166 (docs/HANDOFF.md:260): "The second title's start-up logo is its loading screen: the render
   thread spins until ~1.75 GB of APR reads finish..." Logo 10.9 -> 9.0 s. Source: experiment 0112.
3. **The first title / third title:** **there are the first title runs with it on.**
   - `experiments/0227-apr-load-time-ab/README.md:167`: "`KYTY_BC5_APR_PARALLEL=8` gives the first title no gain: 27.0 and
     26.9 s against 25.3 s for CUR in the same state" (runs AU2/AU3, `raw/AU2-PAR8-start.txt:2`).
   - F286 (docs/HANDOFF.md:381) records the same result and attributes the load time to the page cache.
   - No crash or hang; neutral to slightly slower in n=2.
   - Third title: not found.
4. **Every-title paths:** loading I/O timing and order of APR completions. Exp 0117
   (`experiments/0117-t1-load-timing-hazard/README.md`, Verdict) found the first title's GPU work hangs when its second load
   phase is "served in a different rhythm". That was the mount, not this word, but completion order is the same risk
   class. No GPU or memory-mapping change.
5. **Title-specific?** No data. It is a speed setting (thread count).

## 9. BC5_DIRECT_DMA_SNAPSHOT = "4096" (F172)
1. **Read:** bc5LleAgc.cpp, patch 53903 (`strtoul`; unset = 0, off; "0" = off). The value is a **minimum byte count**,
   not a ring size (the inventory's "ring size in KiB" is wrong). It is applied to "dcb" buffers only (patch 53911).
   Backend: direct.cpp:1269 (`fopt.dma_source_min`, skipped with `legacy_scratch_va`).
   - **On:** the source of every graphics-buffer DMA_DATA of 4096 bytes or more is copied at submission into a shared
     ring, and the IB reads the copy.
   - **Off:** the GPU reads the live source.
2. **Finding:** HANDOFF F172 (docs/HANDOFF.md:266): "The second title's broken menu text ('the scene in a strip') is
   stale CP DMA staging; copying each graphics-buffer DMA source at submission into one shared ring fixes it at no
   measurable cost." Source: experiment 0122.
3. **The first title / third title:** not found. No negative result.
4. **Every-title paths:** yes. It changes GPU submission (rewritten DMA source addresses, an extra copy ring in the BO
   list) and the timing of when data is captured, for every graphics buffer with large DMA_DATA.
5. **Title-specific?** No data. It is a semantic change: it freezes the CPU staging at submit. That is right for the
   second title's rotating staging. It would be wrong if a title writes the source after submit but before the GPU runs
   on purpose (the code comment gives this reason for leaving compute buffers out).

## 10. BC5_DIRECT_FLAT_APERTURE = "1" (F249)
1. **Read:** bc5LleAgc.cpp, patch 53541 ("0", empty or unset = off; "1" or "all" = every program; else a hex program
   list). Called per dispatch at patch 54120.
   - **On:** before a program's first dispatch, the title's code is scanned up to `s_endpgm` (64 KiB window), and each
     `v_med3_u32 ..., 0x70000000` site and its `s_brev_b32 ..., 1` operand are rewritten **in place in guest code
     memory** to the host's aperture bases (patch 53520-53532 and below).
   - **Off:** the code is untouched.
2. **Finding:** HANDOFF F249 (docs/HANDOFF.md:344): "The second title's reflection traversal does not loop: its waves
   are halted by a memory violation at their first BVH stack push, because the title builds the push's FLAT address
   with the console's fixed aperture bases..." Source: experiment 0190. Fix confirmed by F250.
3. **The first title / third title:**
   - F893 (docs/HANDOFF.md:876): the third title's cloth-pass hang is "the second title's flat-aperture stack push
     (F249, F277)... `BC5_DIRECT_FLAT_APERTURE` ... is on only for TITLE2, so it was off here. That is the leading
     cause; a test with the word on (no build) waits for a reboot." The pattern finds 18 sites in each stuck program
     (F893 addendum).
   - Third-title runs with it on: 06:28 on 2026-11-22 (build 389521e4) and the t3rt walk (`k439/t3rt.sh:2,10`). They
     hung at the earlier ~25 s start-up stall before any rewrite: "no 'flat aperture' line"
     (`experiments/0439-third-title/README.md:836`, 851, 862-863). The word is ruled out as the stall's cause (F894).
     Q40 (docs/HANDOFF.md:925) is open.
   - The first title: `k439/ab439bk.sh:9` uses `FLAT_APERTURE=0` as "today's first-title behaviour" (control). Its O arm (on via a
     private kSoft bake, `k439/mkbk439.py:14,422`) has no recorded result in README/HANDOFF (not found).
   - No negative first-title result.
4. **Every-title paths:** yes. It scans every dispatched program once, and wherever the pattern matches it **writes
   guest code memory**. On a title without the pattern it costs one scan per program and changes nothing.
5. **Title-specific?** It is not a learned list in "1" mode. It is a by-pattern rewrite tied to the console ABI
   (aperture constants 0x8000.../0x7000... against amdgpu's 0x2000/0x1000). The program-list mode exists but is not
   used here. A fix, and a candidate for every title (Q40).

## 11. BC5_DIRECT_AMM_PRT = "1" (F260)
1. **Read:** bc5LleAgc.cpp, patch 40166 (`bc5::env_on`), in `mr412_prt_open()`, which is called at device open (patch
   40324) and at reopen (patch 50218).
   - **On:** `g_dev->map_prt_window(0x8000000000, 0x1000000000)`: a PRT mapping over the 64 GiB AMM window, so writes
     to unbacked sparse pages are dropped instead of faulting.
   - **Off (default):** no PRT mapping; such writes fault.
2. **Finding:** HANDOFF F260 (docs/HANDOFF.md:355): "With `BC5_DIRECT_AMM_PRT=1` (F257's fix candidate) one 19-minute
   watched session of the second title had no GPU fault of any kind..."
   - Confidence: "low as evidence for the fix (n = 1)".
   - The cause is in F257 (docs/HANDOFF.md:352, exp 0199). Switch from exp 0102; source of F260: exp 0202.
3. **The first title / third title:** not found. No negative result.
4. **Every-title paths:** yes, at device open. It changes the GPU VM mapping of a fixed 64 GiB range for the whole
   process.
5. **Title-specific?** A fixed address constant (0x8000000000 + 64 GiB). The code ties it to the AMM window; whether
   every title's AMM lies there is not shown in code. It is a fault-suppression mechanism (drop writes to unbacked
   pages). By the maintainer's rule ("GPU fault = bug + record") it is closer to a guard than a fix.

## 12. BC5_DIRECT_SKIP_PGM = "0"
1. **Read:** bc5LleAgc.cpp, patch 54142 (`pgm_list`: hex list parsed with `strtoull`, patch 53982-53994). It drops
   DISPATCH_DIRECT/INDIRECT (0x15/0x16) whose tracked program is in the set (patch 54143-54149).
   - **Unset (default):** empty set, nothing dropped.
   - **"0" (the row):** the set {0}. A dispatch whose tracked `pgm` is 0 (no COMPUTE_PGM seen yet, carried state 0) is
     **dropped**. So the row is not a pure no-op, although the launcher comment says "0 = nothing skipped"
     (`tools/scripts/launchers/play-pkg.sh:127`).
   - Whether pgm==0 dispatches occur in practice: not established.
2. **Finding:** no F row for the "0" value. The skip list's history is F114, F207, F248, F277 and others
   (docs/HANDOFF.md:208, 302, 343, 372). Introduced in exp 0059. Exp 0323 emptied it.
3. **The first title / third title:** not found.
4. **Every-title paths:** only drops (submission) of dispatches with an unknown program, if any.
5. **Title-specific?** The mechanism is a program-address list (title data). As set, it is a test hook. Recommend
   removing the row (unset = nothing skipped).

## 13. BC5_DIRECT_CS_PREFIX = "1" (F321)
1. **Read:** bc5LleAgc.cpp, patch 46597 (`cs_prefix_mode`: unset, empty or "0" = 0; "journal" = 2; else 1). Used at
   patch 48393-48407 and 49672.
   - **On:** in front of a "dcb" that gets no other prefix and dispatches before it sets COMPUTE_PGM_LO
     (`cs_inherit_at`), the GFX queue's tracked compute SH registers (0x204-0x3ff) are replayed with SET_SH_REG.
   - **Off:** the buffer runs with whatever compute registers the shared ring holds (another process's program, F251).
2. **Finding:** HANDOFF F321 (docs/HANDOFF.md:416): "The CS prefix of F253-F266 is integrated as tested..." The code is
   off by default and only the second title's launcher turns it on. Introduced in exp 0195 (patch_0195.diff); F321's
   sources are exp 0254/0259.
3. **The first title / third title:**
   - F321 says "the first title's launchers are unchanged".
   - F315 (docs/HANDOFF.md:410): the first title ran clean S5A/S5C on that build *without* the prefix. The S6N run with the
     prefix (second title) hung after ~140 s, "cause not shown".
   - No first title or third-title run with it on was found.
4. **Every-title paths:** yes, GPU submission. It adds packets to GFX buffers matching the condition, on the shared
   GFX ring.
5. **Title-specific?** No data. It is a generic fix for a ring-sharing hazard.

## 14. BC5_DIRECT_INDIRECT_DRAWS = "multi"
1. **Read:** bc5LleAgc.cpp, patch 53922 (`extra_drop` list) and patch 54086 (presence test).
   - **Unset (code default):** DRAW_INDIRECT 0x24 and the multi-draws 0x2c, 0x38 are **dropped** for every title.
   - **Any other value, "0" included:** 0x2c and 0x38 are dropped.
   - **"multi":** none are dropped.
   - **Also, whenever the word is set at all:** indirect draws 0x24, 0x25, 0x2c and 0x38 that follow a given-up
     CPU-side wait in a chain are dropped (patch 54080-54092). 0x25 is otherwise never dropped by this word.
2. **Finding:** HANDOFF F108 (docs/HANDOFF.md:202): "The second title draws its scene with `DRAW_INDIRECT` and the
   multi-draw packets, which the policy had never reviewed and dropped..." (exp 0054). F112 (docs/HANDOFF.md:206,
   exp 0057/0058) covers "=multi". Introduced in exp 0054 and exp 0057.
3. **The first title / third title:**
   - `experiments/0054-pkg-title-indirect-draws-audio/README.md:30`: "the first title uses `DRAW_INDEX_INDIRECT` (0x25) only,
     which passed". So the extra_drop default does not hit the first title as of that run.
   - With the word set, the first title's 0x25 draws after a given-up wait would start being dropped. No first-title run with it set was
     found.
   - Third title: not found (whether it uses 0x24, 0x2c or 0x38 is unknown).
4. **Every-title paths:** yes, GPU submission (which draws reach the GPU). The **default drops a packet class**, which
   is a risk for any new title that uses 0x24/0x2c/0x38.
5. **Title-specific?** No data. A policy choice: the default is a guard that drops packets, and "multi" removes the
   guard.

## 15. BC5_DIRECT_ALIASES = "1"
1. **Read:** bc5LleAgc.cpp, patch 43458 (`aliases_on`, `bc5::env_on`) and patch 41410 (lazy-release split guard).
   `aliases_apply` is called per submission (patch 53838) and after cuts (patch 44357).
   - **On:** each line "byte lo size" of `~/bc5-work/direct-aliases-pkg.txt` (`alias_path`, patch 43454-43456) is
     mapped a second time at `(byte<<40)+lo` over whatever is mapped there, re-applied at most once a second when the
     mappings change. With LAZY_RELEASE, aliased BOs are then not split unless GUARD_SPLIT is set.
   - **Off (default):** no alias mappings.
   - Learning new lines is dead (`alias_learn` not called, patch 43489).
2. **Finding:** HANDOFF F110 (docs/HANDOFF.md:204): "The second title's tagged addresses are function pointers in its
   constant buffers; mapping its code again under the tag removes the fault, but the GPU then hangs..." Also F112. Source:
   `experiments/0056-address-byte-aliases`.
3. **The first title / third title:** not found with it on (exp 0108/0117 set it only in second-title scripts: `run400.sh:9`,
   `run441.sh:9`). No negative result.
4. **Every-title paths:** yes, if on. It changes GPU memory mapping (extra VA mappings) and blocks lazy-release splits.
5. **Title-specific: yes.** The data is a learned file named for the second title.
   - `experiments/0412-memory-guardian/README.md:2838-2848`: five lines, one real (`0x80 0x11ce000000`, the second
     title's code heap) and four dead junk lines "learned before exp 0195".
   - This is a learned-window mechanism by another name. Exp 0412 names the replacement rule ("map the code heap a
     second time under 0x80"), which is not built.
   - Under the maintainer's no-learned-windows rule this row is a remnant.

## 16. BC5_DIRECT_GPU_CHECK_PRODUCT = "1" (F414, F415)
1. **Read:** backend/src/direct.cpp:593 (`env_on`; "1" or "x_limit[:yz_min]"). Not in the patch. Used at
   direct.cpp:1441, GFX only (`!comp`), and only inside the GPU_CHECK path (`opt.gpu_check_indirect`, direct.cpp:1435).
   - **On:** a COND_WRITE/COND_EXEC staircase refuses dispatches with y or z > 1 and x > 2^16.
   - **Off (default):** no staircase. With GPU_CHECK off it has no effect.
2. **Finding:** HANDOFF F414 (docs/HANDOFF.md:509): "Two guards against the RT-on machine-down classes (F413) are built
   into a private binary and cost RT-off play nothing." F415 (docs/HANDOFF.md:510): 46 min RT-on with no hang. Source:
   experiment 0341. Integration: exp 0342 (`experiments/0342-rt-on-integration/README.md:24`: "the first title's launcher is
   not touched"). The "=0 is off" fix is F767 (docs/HANDOFF.md:759).
3. **The first title / third title:** not found. No negative result.
4. **Every-title paths:** GPU submission of GFX-ring indirect dispatches (more CP packets), only with GPU_CHECK on.
5. **Title-specific?** The limits are constants sized to F403's runaway grids. It is a **guard** (it refuses absurd
   work), not a fix of the cause.

## 17. BC5_DIRECT_SHADOW_LABELS = "1" (F414, F415)
1. **Read:** backend/src/direct.cpp:588 (`getenv(...) != nullptr`: **presence only, "=0" is ON**). Used at
   direct.cpp:1353-1365 (`shadow_labels::apply`, GFX only).
   - **On:** every label an IB both writes and waits on gets a slot in the job's scratch, so the wait reads the host's
     slot. The title's label is still written.
   - **Off (unset):** the wait reads the title's own label.
2. **Finding:** HANDOFF F414/F415 (as row 16). Source: experiment 0341. F767 fixed "=0" for seven other switches, not
   this one (inventory note; F767 lists seven names without SHADOW_LABELS).
3. **The first title / third title:** not found. No negative result.
4. **Every-title paths:** yes. It changes GPU submission (rewritten label addresses and waits in every GFX IB with
   self-synced labels) and the semantics of when a wait completes.
5. **Title-specific?** No data. It is a **guard** against a stray store over a label (F360), not a removal of that
   store. The presence-only read is a bug: NAME=0 cannot turn it off.

## 18. BC5_DIRECT_HOST_INDIRECT = "learn:1100000000" (F432)
1. **Read:** backend/src/direct.cpp:600 (`env_on`). It parses "learn[:hex]" or a hex window (direct.cpp:602-606). Used
   at direct.cpp:1288-1338 (GFX only).
   - **On:** GFX-form dispatches whose base register is 0 after the title's zeroing are resolved by the host against the
     window: the carried base, or the window learned from the title's SET_BASEs, or the fixed `0x1100000000` until one
     is learned. They are rewritten only to a page the host read, else NOP-ed.
   - **Off (default):** the CP reads at the inferred address.
2. **Finding:** HANDOFF F432 (docs/HANDOFF.md:527): "The maintainer played the test 0349 build 18 minutes with RT on: no
   hang, no reset, no kernel line, 39.2 flips/s." It also says "0346 and 0343 did nothing: 0 rewrites". Mechanism from
   exp 0346, integration F433 (docs/HANDOFF.md:528, exp 0350).
3. **The first title / third title:** not found. No negative result.
4. **Every-title paths:** yes, GPU submission. It can NOP or rewrite GFX-ring indirect dispatches, and it costs a
   mapping sort when a candidate appears (direct.cpp:1299-1312).
5. **Title-specific: yes, the value.**
   - `0x1100000000` is an address constant of the second title. F820 (docs/HANDOFF.md:803) names 0x1100000000 as a
     chunk of its `AssetHeap Large`, and the inventory says "the launcher value carries the title's window".
   - "learn" refers to a run-time-learned window from SET_BASEs, not a file.
   - The mechanism is generic. F432 records 0 rewrites, so its effect in that play is unshown.
