# Audit: behaviour keyed on a title id (read-only, main 120153fc; exp/0439-third-title ca9bda02)

Line refs: "patch NNNN" = line in `backend/kytyplus-patches/0001-bc5-lle-agc.patch`. For `src/bc5/switch_defaults.hpp`
the hunk starts at patch 5968 = file line 1, so file line = patch line - 5967.
Title ids: TITLE2 = second title; the first title = image/mount name TITLE1, run-time TITLE_ID TITLE1B (HANDOFF F863);
third title = TITLE3.

## Task 1: title-keyed places OUTSIDE kTitleDefaults

### A. In the patch (emulator)

| # | Where | What is keyed | Kind |
|---|---|---|---|
| 1 | `+++ b/src/bc5/switch_defaults.hpp` patch 6255-6262 (file 288-295), used in `Apply()` patch 6310-6312 and `ApplyTitle()` patch 6265-6274 | `kTitleForced = {BC5_DIRECT_LAZY_RELEASE, BC5_GUARD_SPLIT}`: both are **unset for every process** at start, then only the TITLE2 row sets them (overwrite=1). Effect: TITLE2 always gets `30,eager` / `1`; every other title can never have them, even from the environment. | BEHAVIOUR (one title on, all others forced off) |
| 2 | same file, `DetectTitle`/`TitleIdOf`/`GamePathOf` patch 6216-6252; `KYTY_BC5_TITLE_DEFAULTS=0` patch 6323 | the mechanism: reads `titleId` from `<--game>/sce_sys/param.json` | mechanism (not itself a fix) |
| 3 | `+++ b/src/graphics/presentation/settingsOverlay.cpp` patch 9588-9597 | `if (HostInputTitleId() != "TITLE1")` shows the warning "These steps were measured on the first title ..." in the Video tab's resolution presets. | BEHAVIOUR (UI only, hard-coded id). Likely mismatch (not verified on the box): `HostInputTitleId()` reads TITLE_ID from param.sfo, which for the first title is TITLE1B per F863, so the warning would show on the first title too. |
| 4 | `+++ b/src/graphics/presentation/window/hostInput.cpp` patch 13923-13927 (`HostInputTitleId`), parser patch 14420-14482, writer patch 14270-14275 | input.cfg keys `RenderScale.<ID>`, `RayTracing.<ID>`, `MangoHud.<ID>`; lines of other ids are kept (`m_other_title_scales`). `JobArenaFix.<ID>` (patch 14478-14482) is accepted and ignored (exp 0429: workaround gone). | DATA (per-title settings the user saves from the menu) |
| 5 | `+++ b/src/graphics/presentation/hostMenu.cpp` patch 8180-8195 (`SaveTitleSwitch`), 8624-8632 (RT menu item) | writes `<name>.<TITLE_ID>=on/off` | DATA |
| 6 | `+++ b/src/bc5/title_settings.hpp` patch 6503-6545 (`ValidTitleId`, `Resolve`); hostInput.cpp patch 14565-14627, 14964-14978 (`g_title_dir`) | per-title store `~/bc5-work/menu/titles/<TITLE_ID>/input.cfg` and `window` mode (exp 0435) | DATA |
| 7 | `+++ b/src/bc5/games_list.hpp` patch 4639, 4711, 4802-4805; hostMenu.cpp patch 8133 | menu's installed-games list: title_id/name from param.json | DATA (menu) |
| 8 | `+++ b/src/graphics/presentation/window/window.cpp` patch 15748-15749 | title id in the window caption | DATA |
| 9 | `+++ b/src/libs/libSaveData.cpp` patch 78622-78628 (`get_title_id`), 79358-79360, 79934-79939, 80187-80189 | save paths by the running title's id; a mount for another title's id (the first title asks for TITLEX/sce_sdmemory) uses that id | generic (keyed on the running/asked id, no title gets its own rule) |
| 10 | `+++ b/src/libs/bc5LleAgc.cpp` patch 40464-40474 and 40541-40545 | heap name `"FileSystem"` (a second-title heap, F443/F468/F472) is taken out of LAZY_NAMES and always added to EAGER_NAMES, for every title | BEHAVIOUR keyed on a heap name, not a title id; applies to any title that names a heap "FileSystem" |
| 11 | bc5LleAgc.cpp patch 49605 | `cs == 0x11d0404200` (a second-title program) | diagnostic journal only (no behaviour) |
| 12 | bc5LleAgc.cpp patch 38500-38507, 54142, 54157 | `BC5_DIRECT_SKIP_PGM`, `KYTY_BC5_RT_BUILD_PGM` program lists, `BC5_DIRECT_LAZY_NAMES` / `EAGER_NAMES` (patch 40452, 40528) | generic readers; the lists themselves are title data in the launchers (see B) |
| - | Comments only, no keyed code: memory.cpp patch 29414 (TITLEX), libNpCppWebApi.cpp patch 74595-74599 (TITLE1B module), title_settings.hpp patch 6503 | - | none |

Grep false positives dropped: `BC5_THR_*` (pthread.cpp), `BC5_TLS_*` (runtimeLinker.cpp), `KYTY_BC5_TRAP_LOG`, `KYTY_BC5_TRIGGER_DEADZONE`, `BC5_TIMEOUT_LAYOUT`, `NpSetNpTitleId`/`SceSaveDataTitleId` structs, `sceNpTrophySystemGetTrophyTitleIds`.

### B. backend/ (src, include, tests, policy)

Not found: no code keyed on a title id. Only comments name "the second title" / the first title (e.g. `backend/src/direct.cpp:322,1395`, `backend/include/bc5/host_indirect.hpp:7`, `shadow_labels.hpp:4`, `zero_skip.hpp:2`, `policy.hpp:132`). `backend/kytyplus-patches/input.example.cfg:8` documents the per-title input.cfg keys (DATA).

### C. Launchers and scripts

`experiments/0420-games-menu/play-any.sh` is identical to `tools/scripts/launchers/play-any.sh`; `experiments/0420-games-menu/play-t1.sh` is an older copy of `tools/scripts/launchers/play-t1.sh` (no exp 0439 mount check). Lines below are `tools/scripts/launchers/`.

| # | Where | What is keyed | Kind |
|---|---|---|---|
| C1 | `play-any.sh:50,118-124` | `SECOND_TITLE=TITLE2`: a folder with this id runs through `play-pkg.sh`, **every other title** through `play-t1.sh` | BEHAVIOUR (routing: decides which whole word set a title gets) |
| C2 | `play-any.sh:141-148` | ffpfsc file name's first word `TITLE1`: the first title uses bc5-run.env's module pack; any other image gets `BC5_SYSMODULES_PACK_DIR=$mnt/fakelib` | DATA (path), image-name keyed |
| C3 | `play-t1.sh:9-10` | default image/mount `TITLE1 - T1_4xx.ffpfsc`, `mnt/TITLE1` | DATA (paths) |
| C4 | `play-t1.sh:57` | `BC5_DIRECT_CHAIN=2` (now also in kSoft: duplicate) | BEHAVIOUR for all non-TITLE2 titles via C1; redundant |
| C5 | `play-t1.sh:62` | `KYTY_BC5_APR_READAHEAD=4` | dead: the word is in `kIgnored` (patch 6127) and unset at start |
| C6 | `bc5-run.env.in:7-14,23` (shared settings file, read by every launcher) | The first title's choices as every title's base: `BC5_DIRECT_LAZY_NAMES=orbis_user_malloc`, `BC5_DIRECT_EAGER_NAMES=GpuGarlicMemory,GpuOnionMemory`, `SHADPS4_SYSMODULES_PACK_DIR=.../mnt/TITLE1/fakelib`, `BC5_DIRECT_FLIP_DEFER=1`, `KYTY_GUEST_MEMORY_MB=13824`, `BC5_DIRECT_JOURNAL=min` | heap lists/paths = DATA; `FLIP_DEFER=1` = BEHAVIOUR (every title except TITLE2, which unsets it at play-pkg.sh:93) |
| C7 | `play-pkg.sh` (TITLE2 only, via C1) | words NOT in kTitleDefaults: `:41` LAZY_NAMES +`Wwise,SoundAlloc,FileSystem,UIStringAlloc`; `:46` module pack without PlayGo (`sysmodules-pack-hle-ampr-noplaygo`); `:62` EAGER_NAMES (17 heaps); `:63` `BC5_DIRECT_LEARNED` empty file; `:65` `KYTY_BC5_SAVEDATA_DIR`; `:68` `BC5_DIRECT_CP_COHER_START_DELAY=1` ("never A/B'd"); `:93` unset `BC5_DIRECT_FLIP_DEFER`; `:114` `BC5_DIRECT_GC_TF_RING=1`; `:115` `BC5_DIRECT_GC_HS_OFFCHIP=1`; `:131` `KYTY_BC5_RT_BUILD_PGM` (13 program addresses); `:150` `BC5_DIRECT_TIMEOUT_PROBE=1` (diag, not lean); `:155` `BC5_DIRECT_CROSS_RING_WAITS=all`; `:158` `BC5_DIRECT_RING_DEPS=dcb`; `:162` `BC5_DIRECT_TWO_RING_WAIT_MS=4`; `:166,171` journal/measure words (not lean); `:42` `--fullscreen`; `:177-182` optional `~/bc5-work/bc5-pkg.env` | heap lists, RT program list, paths, fullscreen, savedata dir = DATA; CP_COHER_START_DELAY, GC_TF_RING, GC_HS_OFFCHIP, CROSS_RING_WAITS, RING_DEPS, TWO_RING_WAIT_MS, no-PlayGo pack, FLIP_DEFER unset = BEHAVIOUR one title gets |
| C8 | `play-pkg.sh` duplicates of kTitleDefaults rows | `:64` GUARD_LEARN_LOG, `:69` LAZY_RELEASE (overridden anyway: kTitleForced unsets it), `:70` GUARD_SPLIT (same) and `GUARD_FORGET=10` (dead: kIgnored), `:89` MEC_INDIRECT/GPU_CHECK/**DMA_SYNC**, `:96` REMEMBER_UNMAPPED, `:99` APR_PARALLEL, `:102` DMA_SNAPSHOT, `:125` **FLAT_APERTURE**, `:126` AMM_PRT, `:127` SKIP_PGM=0, `:135` CHAIN, `:138` CS_PREFIX, `:152` INDIRECT_DRAWS/ALIASES, `:156` GPU_CHECK_PRODUCT/SHADOW_LABELS, `:157` HOST_INDIRECT and `SOFT_WAIT_MS=8` (dead: kIgnored), `:73-81` the twenty library words | redundant with the table (launcher copy) |
| C9 | `tools/scripts/t1-route.sh:10` | `_SaveData/TITLE1B` | DATA (test tool) |
| C10 | `tools/bc5-mount` Rust: `pkg/mod.rs:291-726`, `pkg/cnt.rs:223-250`, `pfs.rs:581`, `container.rs:298` | ids in unit tests and doc comments only | none |

## Task 2: exp 0439's planned moves (branch exp/0439-third-title, worktree wt0439, HEAD ca9bda02)

Bake kit generator `experiments/0439-third-title/k439/mkbk439.py` (header lines 6-16; switch_defaults edits 405-437):
- **To kSoft (every title, value "1"), appended after `BC5_DIRECT_ACB_SPLIT_LATE`** (mkbk439.py:414-424):
  `BC5_DIRECT_IB_CHAIN` (:419), `BC5_DIRECT_IB_CHAIN_FLAT` (:420), `BC5_DIRECT_AGC_EOP_IDENT` (:421), `BC5_DIRECT_FLAT_APERTURE` (:422).
- **TITLE2's `FLAT_APERTURE` row is removed** from kTitleDefaults (mkbk439.py:425-428; commit 04cab114).
- **New `#define BC5_T3 "TITLE3"`** (:429-431) and **two kTitleDefaults rows for it** (:435-437): `BC5_DIRECT_DCC_PRESENT=2`, `BC5_DIRECT_EAGER_GPU_WRITE=1`.
- Nothing goes to kDefaults or kFixes. The script asserts none of the five words nor BC5_T3 is already in the header (:407-409).
- README condition for FLAT_APERTURE: `README.md:816-817` "If it passes, the word goes to `kSoft` for every title" (a run with the word on, Q40; the kit already makes the move unconditionally). IB_CHAIN+IB_CHAIN_FLAT+AGC_EOP_IDENT = "the bake set (the top session)" `README.md:632-633`.

**DMA_SYNC:** mkbk439.py does **nothing** with it (no mention). `BC5_DIRECT_DMA_SYNC` stays a TITLE2 kTitleDefaults row (patch 6162, file 195) and acts on the GFX ring only (README:939-941). The "DMA sync candidates" are private switches, off by default, in private build `0a0f31d6` (`k439/be-ds439.diff`, `k439/ds0439.hpp:6-8`), not in any table:
- D `BC5_0439_DMA_SYNC_MEC` (exp 0050's wait on the compute rings too), C `BC5_0439_ARGS_GL2WB`, B `BC5_0439_DMA_DST_BYPASS`, E `BC5_0439_WAVES_UNLIMITED` (diag only) (README:947-952);
- D2 `BC5_0439_DMA_SYNC_LABEL` (also before a label write and at buffer end) (README:985-990);
- F `BC5_0439_KEEP_GDS_SYNC` (keep the title's CP_SYNC on GDS DMA_DATA; a pass "means the strip can go from the shared filter" `policy.cpp:639-646`) (README:979-982).
- `k439/t3one.sh:19-22`: run "fixes" = D+D2+B+C + `BC5_DIRECT_DMA_SYNC=1` set **in the environment**; run "f" = the same with F in place of DMA_SYNC. Verdict not written yet (README:999 "(to come)").

**HANDOFF (main):**
- **F893** (docs/HANDOFF.md:876): after the graphics-mode choice the third title (TITLE3)'s cloth compute pass ("CS Cloth", queue 49) hangs: 7 compute programs push a BVH stack through the console's flat apertures (F249 pattern), and `BC5_DIRECT_FLAT_APERTURE` is on only for TITLE2, so it was off. Leading cause; the test with the word on waits behind F894; confidence medium (addendum: waves halt with memory violations, not loop).
- **F894** (docs/HANDOFF.md:877): start-up stall ~25 s on TITLE3: queue 40's CP sits at a compute-form DISPATCH_INDIRECT (dword 885) whose arguments a DMA_DATA without CP_SYNC copies just before; same race as F107, whose fix `BC5_DIRECT_DMA_SYNC` is TITLE2-only and GFX-only. Also the shared filter strips CP_SYNC from GDS DMA_DATA on all rings; candidates D2/F in `0a0f31d6`; cause a hypothesis, proof run pending.
- F890 (:873): AGC_EOP_IDENT=1 passes the job-system stall (with IB_CHAIN/IB_CHAIN_FLAT on). F891/F892: DCC present fix, ATRAC9 DMC parse.

## Task 3: current rows (main 120153fc, switch_defaults.hpp)

**kFixes** (patch 5994, file 27) - forced; all five are `#ifndef BC5_LEAN` (so lean has an empty kFixes):
`BC5_DIRECT_ACB_STATE_RESTORE=1`, `KYTY_BC5_EVENT_PENDING_CAP=64`, `KYTY_BC5_RANGES_FAST=1`, `KYTY_BC5_PHYSMAP_SORTED=1`, `KYTY_BC5_APR_POSIX=direct`.

**kDefaults** (patch 6018, file 51) - forced (`setenv(..., 1)`):
- not lean: `KYTY_BC5_PTHREAD_FIXES=1`, `KYTY_BC5_SAVEDATA_FIXES=1`, `KYTY_BC5_SAVEDATA_EVENT_CB=1`, `KYTY_BC5_SAVEDATA_SORT=1`, `KYTY_BC5_AUDIO_FIXES=set,room`, `KYTY_BC5_AMPR_WAITS=1`, `KYTY_BC5_VIDEOOUT_STATUS=1`, `KYTY_BC5_EQUEUE_FIXES=1`, `KYTY_BC5_MMAP_SHIM_FIXES=1`, `BC5_R3_MEMSEM_SIGNAL=1`, `BC5_R3_COND_WRITE=1`, `BC5_R3_WAIT_IDLE=1`, `BC5_R3_TS_100MHZ=1`, `KYTY_BC5_TLS_FIXES=1`, `KYTY_BC5_THREAD_SYNC_FIXES=1`, `KYTY_BC5_SEMA_FIXES=1`, `KYTY_BC5_FS_FIXES=1`, `KYTY_BC5_POSIX_RET_FIXES=1`, `KYTY_BC5_FW_NET=1`, `KYTY_BC5_JIT_SHM=1`, `KYTY_BC5_FW_KERNEL=1`;
- every build (incl. lean): `BC5_R3_MPROTECT_GAPS=1`, `BC5_R3_NULL_ARGS=1`, `BC5_R3_RELEASE_HOLES=1`, `BC5_R3_MUNMAP_HOLES=1`, `BC5_R3_FLEX_HINT=1`, `BC5_R3_DMQ_END=1`, `BC5_R3_EXEC_EINVAL=1`, `BC5_R3_QUERY_SIZE=1`, `KYTY_BC5_FW_AUDIO=1`.
- Note: `BC5_R3_SUBMIT_EOP_EVENT` is explicitly NOT a default (patch 6052-6053).

**kSoft** (patch 6094, file 127) - environment wins, every build:
`BC5_DIRECT_JOURNAL_QUIET=1`, `BC5_DIRECT_CHAIN=2`, `BC5_GC_MODE=direct`, `KYTY_BC5_0429_RR=1`, `BC5_DIRECT_ACB_RINGS=4`, `BC5_DIRECT_ACB_QUEUE_STATE=1`, `BC5_DIRECT_ACB_MEC_INDIRECT=1`, `BC5_DIRECT_ACB_STATE_NO_WALK=1`, `BC5_DIRECT_ACB_SPLIT_LATE=3`.

**kIgnored** (patch 6118, file 151; unset at start) for reference: not lean `BC5_FAULT_RECORD`, `BC5_DIRECT_COMPUTE_RING`, `BC5_DIRECT_PREFIX_ALL`, `BC5_DIRECT_SOFT_WAIT_MS`, `KYTY_BC5_AMM_SETBUFFER_GUARD`, `KYTY_BC5_APR_READAHEAD`, `KYTY_BC5_APR_SYNC`, `KYTY_BC5_AT9_VIBRATION`, `KYTY_BC5_NP_SESSION_V2`, `KYTY_BC5_PAD_PW_PROPS`, `KYTY_BC5_PAD_RUMBLE_FALLBACK`, `KYTY_BC5_SWITCH_DEFAULTS`, `BC5_GUARD_FORGET`; every build `BC5_DIRECT_IB_MAX_DW`. Lean also unsets `BC5_DIRECT_DRAW_ARGS_JOURNAL` (patch 6313-6316).

**kTitleDefaults** (patch 6155-6210, file 188-243): 38 rows, all `BC5_T2 "TITLE2"` (18 direct-path words + 20 library words); no other title.

Already every-title among the generic words: everything above in kFixes/kDefaults/kSoft. TITLE2-only today and generic in form: MEC_INDIRECT, GPU_CHECK, DMA_SYNC, REMEMBER_UNMAPPED, APR_PARALLEL, DMA_SNAPSHOT, FLAT_APERTURE, AMM_PRT, CS_PREFIX, INDIRECT_DRAWS, ALIASES, GPU_CHECK_PRODUCT, SHADOW_LABELS, HOST_INDIRECT, GUARD_LEARN_LOG, the 20 library words, plus the launcher-only words in C7.
