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
| E. words from the hunt for the hang classes F403 and F813 | `BC5_DIRECT_ARGS_COPY`, `_ARGS_FLUSH`, `_ARGS_FLUSH_DRAWS`, `_ARGS_WB`, `_CHAIN_HOLD_US`, `_DCB_WAIT_MS`, `_FL_SERIAL`, `_FL_VGT_FLUSH`, `_FORCE_START_000`, `_GPU_CHECK_YZ`, `_GPU_CHECK_ZERO`, `_PIECES_NO_CLEAR`, `_TF_DEFAULT` | 13 | **CORRECTED 2026-11-13 (see below): both classes are OPEN in HANDOFF, so this is not "a fault that is gone".** Per word in the section below | see below | see below |
| F1. AMM commands with a cost and no user | `KYTY_BC5_AMM_PRT_CMDS`, `_AMM_EXTRA_CMDS` | 2 | no run: audit row A6 (a mutex and a map node per 16 KiB page on every AMM call; the second title imports none): delete | 0 | 0 |
| F2. AMM words that need the wall or a caller | `KYTY_BC5_AMM_SCATTER`, `_AMM_SETBUFFER_MAP` | 2 | SCATTER belongs to exp 0412's memory-wall plan (it acts only below 13,824 MiB); SETBUFFER_MAP stays an opt-in until a title makes that call with real arguments | 0 here | 0 |
| G. need a new form or a scene, not a run of today's build | `KYTY_BC5_ANON_SYNC` (the `events` form, not built), `_MAP_RECORDS` + `_MAP_RECORDS_CHECK_MS` (the form without the copy), `BC5_R3_SUBMIT_EOP_EVENT` (the walk never reaches its path: a scene that does), `KYTY_BC5_PAD_TOUCH` (the maintainer's finger on the touchpad) | 5 | their owners' next builds; PAD_TOUCH is one minute of the maintainer at the box | 0 | 0 |

Sum: 2 + 23 + 2 + 3 + 3 + 2 + 6 + 13 + 2 + 2 + 5 = 63.

## Correction to group E (2026-11-13, after reading the records)

The first form of this plan said these words were "fix candidates for hang classes that do not recur" and proposed
deleting all of them by rule. That premise was WRONG. `docs/HANDOFF.md` on 2026-11-13: F403 "OPEN ... neither 'gone'
nor 'still there' is shown" (it came only in arms with the zero skip on, 3 in 19 against 0 in 10, and the skip is out
since 2026-11-12); F813 (the draw that never ends) "OPEN"; Q20 lists both as what stays open. No fix for either is in
the shared builds. The maintainer's decision "Próby z polowania na dawne zawieszenia => usunąć z kodu" was put to him
on this plan's wording, so it goes back to him with the records:

| Word | What it was | The record's last word | Contradicts a plain delete? |
|---|---|---|---|
| `BC5_DIRECT_ARGS_WB` | fix candidate, F403 sub-class B | F583: a 36.6-minute play "had no F403"; F584: "A second long play ... is the decisive next step"; F813 names `ARGS_WB=all` as the test standing, cost unmeasured | **yes**: the only word of the group with a measurement in its favour, and its second run is owed |
| `BC5_DIRECT_FL_SERIAL` | fix candidate, the draw class (F813) | audit B10: 0 hangs in 8 with it, 0 in 10 without, about 3 % slower; "integrate (default off) so it can be tested when the class returns" | **yes** while F813 is open |
| `BC5_DIRECT_FL_VGT_FLUSH` | fix candidate, the draw class | "built, never set in an arm" | yes: never run |
| `BC5_DIRECT_ARGS_FLUSH`, `_ARGS_FLUSH_DRAWS` | fix candidates (F616 ranks them; F617) | built, no GPU run | yes: never run |
| `BC5_DIRECT_ARGS_COPY` | a mechanism test, then a fix candidate with WB | F568: "The copy alone must not be used"; its low-VA form "Not relinked, not run" | the plain form no; the low-VA form was never run |
| `BC5_DIRECT_GPU_CHECK_YZ` | a guard for runaway grids (F403-A) | F556: "Per F555 it would not have caught 12:12"; untested on the GPU | no |
| `BC5_DIRECT_GPU_CHECK_ZERO` | a guard for a hypothesis (F549: "not supported, not refuted") | F548: "Not built on the box, not run on the GPU" | no |
| `BC5_DIRECT_FORCE_START_000` | a guard | F564: the class "hung again" with it on | no: it did not prevent the hang |
| `BC5_DIRECT_PIECES_NO_CLEAR` | a mechanism test | F609: "would therefore not isolate CLEAR_STATE" | no |
| `BC5_DIRECT_TF_DEFAULT` | the host's default TF ring | exp 0189: "is not needed by this title"; but `hs_offchip_force()` is called only inside its block (exp 0388) | check against exp 0418's table before cutting |
| `BC5_DIRECT_CHAIN_HOLD_US`, `_DCB_WAIT_MS` | timing words | see `launcher-words.md`; F285 measured `DCB_WAIT_MS=100`: 0 give-ups against 13, and 27 s of long frames against 8 | live: his decision |

Tonight's GPU hang of candidate F at 601 s (README section 13: an acb and a dcb timed out, no page fault) is of the
kind these classes describe. Until the deciding series says otherwise, the four fix candidates that have never had
their run (`ARGS_WB`'s second play, `FL_SERIAL`, `FL_VGT_FLUSH`, `ARGS_FLUSH`) are exactly what "fixes first, then
test" would put into one build for that hang. Proposal: delete the five that the records themselves discard
(`GPU_CHECK_YZ`, `GPU_CHECK_ZERO`, `FORCE_START_000`, `PIECES_NO_CLEAR`, plain `ARGS_COPY`); keep the fix candidates
until the hang at 601 s is understood, then run them or delete them. Seven of the nine are read in
`backend/src/direct.cpp`, so cutting their code is a backend change.

Other corrections from the same reading: the batch-2 library tables were NOT blamed for the hang of run r7all
("r7all's extras: not a plausible cause"; "No path from them to this GPU pass is known"; the same class came without
them); their only clean run is one start arm of the second title (t7tab), and `NPTUS_FRIENDS_RUN` and `USBD_ALLOW`
were set in no arm. `BC5_GUARD_PIN_CAP` has one measurement (pin -290 MiB, the picture not looked at).
`KYTY_BC5_SEMA_TARGETED_WAKE` aims at F451, which is open.

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
