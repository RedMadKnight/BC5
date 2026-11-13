# BC5 environment switches: inventory summary (2026-11-13, main, patch 27b6416f)

Rows: `switch-inventory.tsv` in this directory, 266 names: 254 quoted in patch 0001's added lines, 12 read in `backend/src/direct.cpp` (one of them is in both), and `BC5_DIRECT_LEARNED`, set by a launcher and read by nothing. The rest of `backend/` reads none (the count of 194 was not reproduced). No switch is read only by `backend/tests` or `backend/experiments`. The patch's other ~450 `BC5_*` names are constants and macros, not switches.

## Counts

| State today | n | | Disposition | n |
|---|---|---|---|---|
| on in code: kFixes 5, kDefaults 31, hard-coded at the read site 13 | 49 | | KEEP-DIAG | 67 |
| tuning/config value with a code default | 14 | | UNDECIDED | 62 |
| on via launcher only (play-pkg.sh 56, play-any.sh 1; play-astro.sh sets 4 of them) | 57 | | HARDEN | 52 |
| on via `bc5-run.env` only (inferred, file not read) | 4 | | DELETE | 30 |
| on in test shortcuts only (e10-menu, 0412-fast9, 0412-astro-cap) | 13 | | title-specific | 28 |
| off everywhere | 127 | | PROMOTE | 17 |
| per-title input file (`KYTY_BC5_JOB_ARENA_FIX`) / not read | 1 / 1 | | KEEP-CONFIG (outside the asked set) | 10 |

By kind: fix/behaviour 146, diagnostic 63, tuning 17, configuration 16, test hook 13, kill-switch 11. Answer to the question: 36 tested fixes became code defaults in the last two days (exp 0413/0416) and none of them has lost its option yet (52 HARDEN rows); 44 fix or tuning words are on only because `play-pkg.sh` says so; 30 refuted or superseded words are still compiled in.

## PROMOTE (17): verdict positive, on only through a launcher or off

- `BC5_DIRECT_CHAIN=2`: F224, 33 to 48 flips/s; the only fix both title launchers set. `play-any.sh`'s directory branch gets 0.
- `BC5_GC_MODE=direct`: the whole direct path; set only in `bc5-run.env` (inferred).
- Second title's launcher only: `BC5_DIRECT_MEC_INDIRECT`, `_GPU_CHECK`, `_DMA_SYNC` (F91, F106, F107); `_DMA_SNAPSHOT=4096` (F172); `_REMEMBER_UNMAPPED` (F163); `_GC_TF_RING` (F248); `_FLAT_APERTURE`, `_AMM_PRT` (F249-F260); `_CS_PREFIX` (F253/F254); `_GPU_CHECK_PRODUCT`, `_SHADOW_LABELS` (F414/F415); `_GC_HS_OFFCHIP` (F786, one run and his look); `KYTY_BC5_APR_PARALLEL=8` (F166). None has an ASTRO BOT run that I found.
- `BC5_R3_SUBMIT_EOP_EVENT`: audit row A9 positive, held back for F825, whose fix is in since 11-13; still off in `play-pkg.sh`, on in two shortcuts.
- `BC5_GUARD_LEARN_LOG=2`: at 2 it also stops `alias_learn` (patch line 36918); without the word a GPU fault adds an alias window again.

## Launcher-only fixes (44): a new launcher or shortcut silently loses them

- The 14 PROMOTE fixes above that `play-pkg.sh` sets.
- The 20 words of audit rows A15/A16/A17/A21/A22 (SaveData memory, Http2, pad open-ext, Json2, Ult, User/SystemService, AudioOut/In checks, Ngs2, FW_PAD, six `KYTY_BC5_LOAD_*`): title-specific, because four or more of them on crash ASTRO BOT at 5-6 s (exp 0413, cause not found).
- Title data: `BC5_DIRECT_ALIASES`, `_INDIRECT_DRAWS=multi` (unset, the code drops ops 0x24/0x2c/0x38), `_HOST_INDIRECT=learn:1100000000`.
- Never settled: `BC5_DIRECT_CP_COHER_START_DELAY` (never A/B'd), `_LAZY_RELEASE=30,eager` + `BC5_GUARD_SPLIT`, `_CROSS_RING_WAITS=all`, `_RING_DEPS=dcb`, `_TWO_RING_WAIT_MS=4`.
- `BC5_GUARD_FORGET=10`: audit row C6 says "adds nothing measurable"; DELETE. Not counted as fixes but lost the same way: `BC5_DIRECT_EAGER_NAMES`, `_LAZY_NAMES`, `KYTY_BC5_RT_BUILD_PGM`, `KYTY_BC5_SAVEDATA_DIR`.

## UNDECIDED fixes (51 of the 62)

- Never tested on the box, or never alone: `BC5_DIRECT_ARGS_FLUSH`, `_ARGS_FLUSH_DRAWS`, `_GPU_CHECK_YZ`, `_GPU_CHECK_ZERO`, `_FL_VGT_FLUSH`, `_TF_DEFAULT`, `_CP_COHER_START_DELAY`, `BC5_GUARD_MLOCK`, `BC5_GUARD_PRT_BG`, `KYTY_BC5_PAD_TOUCH`, `KYTY_BC5_AMM_SETBUFFER_MAP`, `KYTY_BC5_AMM_PRT_CMDS`/`_EXTRA_CMDS`, and the 22 batch-2 ports of audit row A23 (20 `KYTY_BC5_LOAD_*`, `VOICE_PORTS`, `NPTUS_FRIENDS_RUN`: one start arm, never in play).
- Tested inconclusively: `BC5_DIRECT_ARGS_WB` (F575/F813), `_ARGS_COPY` (F571), `_FORCE_START_000`, `_FL_SERIAL` (0/8 against 0/10), `_LAZY_RELEASE` + `BC5_GUARD_SPLIT`, the pin cap (3 words, "nobody looked at the picture"), `KYTY_BC5_AMM_SCATTER` (4/7), `KYTY_BC5_SEMA_TARGETED_WAKE`, `KYTY_BC5_EVENT_COALESCE_SAME`, `KYTY_BC5_MAP_RECORDS` (correct, saves nothing). State unknown on one ring: `BC5_DIRECT_CROSS_RING_WAITS`, `_RING_DEPS`. Also `BC5_DIRECT_HEAP_GUARDS` (clean with and without).

## DELETE (30)

- Learned windows and recovery: `BC5_DIRECT_LEARNED`, `_LEARN_GUEST_ONLY`, `_RESET_LABELS`, `_RESET_LABELS_ADD`, `_RESET_REPLAY_ACB`, `_RESET_LABEL_JOURNAL`, `BC5_GUARD_APPLY_MIN_MS`, `BC5_GUARD_FORGET` (F820, F821).
- Zero skip (F818): `BC5_DIRECT_ZERO_SKIP`, `_ZERO_NAMES`, `BC5_GUARD_ZSKIP_POLL_SUBMIT`. Catchers that answered: `BC5_DIRECT_ACB_INHERIT` (+2 caps), `_FL_MESHLET_SAMPLE`, `_FL_SKIP_ES`, `BC5_R3_DROP_CATCH`, `BC5_R3_REWIND_CATCH`.
- Failed or refuted: `BC5_DIRECT_ACB_CS_PREFIX`, `_SPI_REQ_CTRL_PS`, `KYTY_BC5_MEMORY_FROM_PARAM`, `BC5_GUARD_MAP_RULE` (F819), `BC5_GUARD_FILE`/`_FILE_ROOT`/`_PSI`, `KYTY_BC5_ANON_SYNC`(+`_MS`, F824), `KYTY_BC5_NAMES_FAST`, `KYTY_BC5_VMA_FAST` (F823), `KYTY_BC5_MIN_FLIP_RATE` (F247).

## Inconsistent

- Set and not read: `play-pkg.sh` exports `BC5_DIRECT_LEARNED`; patch 27b6416f has no read of it. Set differently: `BC5_R3_SUBMIT_EOP_EVENT` on in two shortcuts, off in `play-pkg.sh`. The two title launchers share only `BC5_DIRECT_CHAIN`.
- Rejected words still on in shortcuts: the four e11 recovery words `=1` (0412-fast9, repo copy of its script), `BC5_R3_DROP_CATCH`/`_REWIND_CATCH=1`, `BC5_DIRECT_ACB_INHERIT=journal`, `KYTY_BC5_AMM_PRT_CMDS`/`_EXTRA_CMDS=1` (e10-menu and 0412-fast9).
- Two reading rules. Thirteen words are on at any value, `=0` included: `BC5_DIRECT_ALIASES`, `_AMM_PRT`, `_DMA_SYNC`, `_GPU_CHECK`, `_MEC_INDIRECT`, `_REMEMBER_UNMAPPED`, `_SHADOW_LABELS`, `_FLIP_DEFER`, `_OFFCHIP_SECOND`, `KYTY_BC5_APR_SYNC`, `_NO_PAD_AUDIO`, `_PAUSE_ON_BACKGROUND`, `_SETTINGS_OPEN`; `BC5_DIRECT_CROSS_RING_WAITS=0` and `_RING_DEPS=0` also read as on. `BC5_DIRECT_ZERO_SKIP` is read under both rules (patch lines 35520 and 35838).
- Redundant words: `BC5_DIRECT_SOFT_WAIT_MS=8`, `KYTY_BC5_APR_READAHEAD=4` (astro), `BC5_DIRECT_SKIP_PGM=0`; the shortcuts repeat the kDefaults names. `BC5_DIRECT_TWO_RING_WAIT_MS=4` was measured on ASTRO BOT (exp 0133) and is set only for the second title.
- `backend/kytyplus-patches/README.md` names about 100 `BC5_*` words that no read site in the patch or backend quotes (`BC5_DIRECT_STAGE`, `_ASYNC`, `_PIECES_FULL`, `_TS_SCALE`, ...).

## Not verified

- `~/bc5-work/bc5-run.env`, `bc5-pkg.env` and `input.cfg` were not among the copies; their words are inferred from exp 0415 `raw/y7-environ.txt` (2026-11-12). The e10-menu and 0412 shortcuts run private launchers; for fast9 I used the repo's `experiments/0412-memory-guardian/play-guard-0412.sh`, not the box's file, and did not check which binary e10-menu starts.
- Verdicts come from the audit of exp 0413, HANDOFF rows and launcher comments; I did not open every experiment README. "ASTRO BOT not checked" means I found no run, not that none exists. Whether `CROSS_RING_WAITS`, `RING_DEPS` and `TWO_RING_WAIT_MS` still act on one ring was not traced in the code.
- Nothing was built or run; no box access.
