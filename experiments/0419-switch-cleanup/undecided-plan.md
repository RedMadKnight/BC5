# Experiment 0419: how to settle the 63 words without a verdict

Asked by the top session on 2026-11-13. The 63 are `undecided-list.md`'s 62 less exp 0415's four tuning words (deleted
in E/F) plus `KYTY_BC5_ANON_SYNC`, `BC5_GUARD_FORGET`, `BC5_GUARD_MAP_RULE`, `BC5_DIRECT_SPI_REQ_CTRL_PS` and
`BC5_R3_SUBMIT_EOP_EVENT`. Grouped by what would give a verdict. An arm is one run of the private runner on candidate
F's binary with the pad recorded: the second title's walk to G+240 (about 6 minutes of box time), the cutscene arm
(about 7.5), ASTRO BOT 120 s (about 2.5). A run answers "does it break, does it cost"; it cannot prove a fix for a
fault that no longer happens, so some groups get a decision and no run.

| Group | Words | n | What settles it | Arms | Box minutes |
|---|---|---|---|---|---|
| already gone in F | `BC5_DIRECT_CP_COHER_START_DELAY`, `_SPI_REQ_CTRL_PS` | 2 | exp 0418's start-state table writes both always; nothing reads the words | 0 | 0 |
| A. the batch-2 library tables | 20 `KYTY_BC5_LOAD_*` (CAMERA ... WEBBROWSERDIALOG), `_NPTUS_FRIENDS_RUN`, `_VOICE_PORTS`, `_USBD_ALLOW` | 23 | all on at once on both titles; clean = they are harmless and can go into a table as on, or stay off and lose the option (no title here loads these libraries); a failure is bisected by halves | 2 (+ up to 5 for a bisect) | 9 (+ up to 25) |
| B. exp 0416's two correctness ports | `KYTY_BC5_SEMA_TARGETED_WAKE`, `_EVENT_COALESCE_SAME` | 2 | both on, both titles; clean and no slower than the control = promote | 2 | 9 |
| C. left from two rings | `BC5_DIRECT_CROSS_RING_WAITS`, `_RING_DEPS`, `_TWO_RING_WAIT_MS` | 3 | the three turned off for the second title (walk and cutscene arm); clean and the same flip rate = they do nothing on one ring: rows and code go | 2 | 14 |
| D1. exp 0412's memory words that run every day | `BC5_DIRECT_LAZY_RELEASE` + `BC5_GUARD_SPLIT`, `BC5_GUARD_FORGET` | 3 | one walk and one cutscene arm without each (pin, orphans, available: exp 0412 reads them) | 4 | 27 |
| D2. exp 0412's and exp 0417's built-in alternatives | `BC5_DIRECT_HEAP_GUARDS`, `BC5_DIRECT_MAX_BO_MIB` | 2 | one walk each (`HEAP_GUARDS=0`; `MAX_BO_MIB=16` against unset) | 2 | 12 |
| D3. exp 0412's words with no user | `BC5_GUARD_PIN_CAP`, `_CAP_ACT`, `_CAP_NAMES`, `BC5_GUARD_MLOCK`, `BC5_GUARD_PRT_BG`, `BC5_GUARD_MAP_RULE` | 6 | no run: log-only or inert today, and K1r (default on in F) is the rule that replaced MAP_RULE and PRT_BG; exp 0412's word to delete | 0 | 0 |
| E. fix candidates for hang classes that do not recur | `BC5_DIRECT_ARGS_COPY`, `_ARGS_FLUSH`, `_ARGS_FLUSH_DRAWS`, `_ARGS_WB`, `_CHAIN_HOLD_US`, `_DCB_WAIT_MS`, `_FL_SERIAL`, `_FL_VGT_FLUSH`, `_FORCE_START_000`, `_GPU_CHECK_YZ`, `_GPU_CHECK_ZERO`, `_PIECES_NO_CLEAR`, `_TF_DEFAULT` | 13 | no run can show a fix for a fault that is gone. Decision by rule: a word whose fault has not been seen since its experiment is deleted with its code; if a fault of that class comes back, the fault record names it and the fix is built again from the experiment's record. `_TF_DEFAULT` is superseded by exp 0418's table | 0 | 0 |
| F1. AMM commands with a cost and no user | `KYTY_BC5_AMM_PRT_CMDS`, `_AMM_EXTRA_CMDS` | 2 | no run: audit row A6 (a mutex and a map node per 16 KiB page on every AMM call; the second title imports none): delete | 0 | 0 |
| F2. AMM words that need the wall or a caller | `KYTY_BC5_AMM_SCATTER`, `_AMM_SETBUFFER_MAP` | 2 | SCATTER belongs to exp 0412's memory-wall plan (it acts only below 13,824 MiB); SETBUFFER_MAP stays an opt-in until a title makes that call with real arguments | 0 here | 0 |
| G. need a new form or a scene, not a run of today's build | `KYTY_BC5_ANON_SYNC` (the `events` form, not built), `_MAP_RECORDS` + `_MAP_RECORDS_CHECK_MS` (the form without the copy), `BC5_R3_SUBMIT_EOP_EVENT` (the walk never reaches its path: a scene that does), `KYTY_BC5_PAD_TOUCH` (the maintainer's finger on the touchpad) | 5 | their owners' next builds; PAD_TOUCH is one minute of the maintainer at the box | 0 | 0 |

Sum: 2 + 23 + 2 + 3 + 3 + 2 + 6 + 13 + 2 + 2 + 5 = 63.

## Two chains after the swap

Both on F's shared binary, pad recorded, one lock line each, a control walk first (the day's own number for F).

| Chain | Arms | Box time |
|---|---|---|
| 1 (libraries, ports, one ring) | control walk; A on ASTRO BOT and on the walk; B on ASTRO BOT and on the walk; C on the walk and on the cutscene arm | 7 arms, about 40 minutes (a bisect of A, if it fails, is a third chain) |
| 2 (memory words; exp 0412 reads the pin and orphan numbers) | walk and cutscene arm without `BC5_GUARD_FORGET`; the same without `BC5_DIRECT_LAZY_RELEASE` and `BC5_GUARD_SPLIT`; walk with `BC5_DIRECT_HEAP_GUARDS=0`; walk with `BC5_DIRECT_MAX_BO_MIB=16` | 6 arms, about 40 minutes |

After the two chains 33 words have a run behind their verdict (A 23, B 2, C 3, D1 3, D2 2). 23 more are decided
without a run (the 2 already gone, D3 6, E 13, F1 2), each by its owner's or the maintainer's word. 7 stay open
with a named next step (F2 2, G 5). One run each is a start, not a proof: a word that changes memory or speed gets a
second run before it is hardened, as K1r did.
