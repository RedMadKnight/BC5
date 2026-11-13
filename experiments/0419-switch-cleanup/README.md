# Experiment 0419: switch cleanup

Claimed 2026-11-13 by the integration session (exp 0417) on the top session's order. The maintainer's question:
"te wszystkie przełączniki które robisz domyślnie wyłączone, po moich testach integrujesz jako włączone i wyrzucasz
jako opcje, czy zapominasz o tym, że w ogóle są?"; on "prepare the next build with the switches put in order
(rejected ones deleted, checked ones promoted)?": "Tak, przygotuj".

## Question

Of the 266 environment switches the patch and the backend read, which can lose their option, which become code
defaults, and which have no verdict; and what does a build that does this look like?

## Setup

Base: the shared patch 27b6416f (candidate B, in the shared builds since 2026-11-13 15:47). Laptop only; the box was
used for one read (copies of the launchers, `bc5-run.env`, `input.cfg`, the desktop shortcuts and the two private
launchers they start). Nothing of this experiment has been compiled for the host or run.

- `switch-inventory.tsv`, `switch-inventory-summary.md`: the top session's inventory, made by a subagent, NOT
  verified. Every row used below was checked first: by the owner of the word (`owners-verdicts.md`), by a second read
  of the project's records (25 of the 30 DELETE rows confirmed, 5 not), and at the read site in the tree.
- The candidate is called **D** (C is exp 0417's save-data-memory candidate, patch 1689b7da). D = B + three
  generators, patch **a4d49749** (`tree-candidate-D-a4d49749.md5`; the patch and the unit 2c43382d are in the
  sessions' notes folder). `grep -c 'exp 0372'` = 5.

## Result

### 1. DELETE, phase 1 (`mkdel0419.py`): 29 words can no longer be set

Each read of the environment becomes the constant the switch had when unset (33 read sites). The option is gone and
the compiler drops what it guarded; the dead code and its journal texts are still in the source. Phase 2 (removing
that code) is not done: it wants a compiler, and the candidate should run first.

| Group | Words | Verdict behind it |
|---|---|---|
| recovery after a GPU reset | `BC5_DIRECT_RESET_LABELS`, `_RESET_REPLAY_ACB`, `_RESET_LABEL_JOURNAL`, `_RESET_LABELS_ADD`, `_LEARN_GUEST_ONLY` | F821 and the maintainer's rule of 2026-11-13 (no recovery as a fix); exp 0412: unreachable while the fault record is on |
| learned from a fault | the call of `alias_learn` (exp 0056) is removed: a GPU fault at a tagged address no longer adds an alias window | the maintainer: no learned windows, in any form |
| zero skip | `BC5_DIRECT_ZERO_SKIP`, `_ZERO_NAMES`, `BC5_GUARD_ZSKIP_POLL_SUBMIT` | F818 (unsound by design); exp 0412: delete |
| catchers that answered | `BC5_DIRECT_ACB_INHERIT` (+ `_INHERIT_PROG_CAP`, `_INHERIT_CENSUS_CAP`), `_FL_MESHLET_SAMPLE`, `_FL_SKIP_ES`, `BC5_R3_DROP_CATCH`, `BC5_R3_REWIND_CATCH` | audit rows B4, B11, B8, A10 |
| failed or refuted | `BC5_DIRECT_ACB_CS_PREFIX` (B3: 3 guest CPU crashes), `KYTY_BC5_MEMORY_FROM_PARAM` (A25), `KYTY_BC5_MIN_FLIP_RATE` (F247: the cutscenes run at 1.00x without it; the code comment that says otherwise is exp 0183's and stale) | as cited |
| exp 0412's | `BC5_GUARD_FILE`, `_FILE_ROOT`, `BC5_GUARD_PSI`, `BC5_GUARD_APPLY_MIN_MS` | its owner: never moved the wall / dead |
| exp 0415's | `KYTY_BC5_NAMES_FAST`, `_VMA_FAST`, `_RING_SPIN_US`, `_MUTEX_SPIN_US`, `_TIMERSLACK_NS`, `_LOAD_DELAY`, `_RING_POLL_US` (200 stays in the code) | its owner, 2026-11-13 |

Kept against the inventory, with the reason:

| Word | Inventory | Why it stays |
|---|---|---|
| `KYTY_BC5_ANON_SYNC`, `_ANON_SYNC_MS` | DELETE | exp 0415: `verify` is a diagnostic, the next form reuses the word; `thread` must never be promoted |
| `BC5_GUARD_FORGET` | DELETE | exp 0412: in every cutscene arm; one arm without it is owed. It is 10 in the daily launcher (moved to the title's table) |
| `BC5_GUARD_MAP_RULE` | DELETE | F819 says "off", not "remove"; `BC5_GUARD_PRT_BG` acts only with it. exp 0412's statement that neither is read in B is REFUTED: `env_digit` reads all three at lines 2075-2084 of the unit |
| `BC5_GUARD_LEARN_LOG` | PROMOTE | its value 2 only stopped `alias_learn`, which is no longer called, so the word has no behaviour left; it stays readable because the fast9 shortcut refuses to start on a binary without that text (decision 2) |
| `BC5_DIRECT_SPI_REQ_CTRL_PS` | DELETE | one confounded play is the only verdict, and exp 0418 found Mesa and PAL both write the value and plans the word |
| `BC5_DIRECT_LEARNED` | DELETE | read by nothing; it is only a launcher line (out in the prepared launcher) |

### 2. PROMOTE (`mkdefs0419.py`, `title_defaults.inc`): 2 general, 45 per title, 0 by guess

| Where | Words | Why |
|---|---|---|
| `kDefaults` (every title) | `BC5_DIRECT_CHAIN=2`, `BC5_GC_MODE=direct` | the only two with daily use on BOTH titles |
| the title's table (PPSA03671) | 25 direct-path words and the 20 library words of audit rows A15-A22, with the launcher's values | no ASTRO BOT run is on record for 14 of the 17 PROMOTE words, and four or more of the 20 library words end ASTRO BOT at 5-6 s; per title this is the same behaviour as today, from the code instead of the launcher |
| stay in the launcher | the heap-name lists, the RT program list, paths, diagnostics (18 words) | title data and paths |

The title id is read at process start from `sce_sys/param.json` of the `--game` directory, before any static
initializer; a value in the environment still wins, `NAME=0` turns a row off, `KYTY_BC5_TITLE_DEFAULTS=0` skips the
table. One stderr line names the title and the count. `BC5_R3_SUBMIT_EOP_EVENT` is NOT promoted: its one run on the
new shared build (exp 0417 section 14) never reached the path it changes.

Own tests on the laptop (VS clang++): `test0419defs.cpp` all ok (the command-line and JSON readers, 45 rows, the
environment wins, an empty value counts as set, `KYTY_BC5_SWITCH_DEFAULTS=0`); `cmplaunch0419.py`: **46 launcher words
are in the tables with the same value, 0 problems**, 18 stay.

### 3. One reading rule (`mkrule0419.py`): 15 words, 16 read sites

Unset, empty or "0" is off for `BC5_DIRECT_ALIASES`, `_AMM_PRT`, `_DMA_SYNC`, `_GPU_CHECK`, `_MEC_INDIRECT`,
`_REMEMBER_UNMAPPED`, `_FLIP_DEFER`, `_OFFCHIP_SECOND`, `_CROSS_RING_WAITS`, `_RING_DEPS`, `KYTY_BC5_APR_SYNC`,
`_NO_PAD_AUDIO`, `_PAUSE_ON_BACKGROUND`, `_SETTINGS_OPEN`. No launcher, shortcut or script of the repository sets any
of them to 0 or empty today (checked), so nothing that runs changes. Not done: `BC5_DIRECT_SHADOW_LABELS` is read in
`backend/src/direct.cpp`; changing it changes the shared backend archive (decision 4).

### 4. HARDEN: `harden-list.md`, 52 options to remove in the swap after D

Not touched in D (a bisect of D needs them). The list is the inventory's and each row still needs its read site
checked before that swap.

### 5. Launchers and shortcuts (prepared, NOT installed)

`mklaunch0419.py` -> `play-pkg-0419.diff` (46 changed lines: 27 words out of the export lines, the loop of 20, the
`AMM_PRT` line) and `play-astro-0419.diff` (2 words). They need D's binary: on today's shared builds they would run
without the fixes. Until they are installed the old launchers work unchanged on D (they set the same values).

On the box's desktop on 2026-11-13 (read from the box, not from the repository):

| Shortcut | Starts | Rejected words it sets today |
|---|---|---|
| "BC5 emulator (0412 fast9 bez Plasmy)" | `exp0412/play-guard-0412.sh fast9` on the SHARED build | the four recovery words `=1` (line 54 of that script), `BC5_R3_DROP_CATCH=1`, `_REWIND_CATCH=1`, `BC5_DIRECT_ACB_INHERIT=journal`, `KYTY_BC5_AMM_PRT_CMDS=1`, `_EXTRA_CMDS=1` |
| "BC5 emulator (e10 menu)" | the emulator with words on its Exec line | `BC5_DIRECT_ACB_INHERIT=journal`, `BC5_R3_DROP_CATCH=1`, `_REWIND_CATCH=1`, `KYTY_BC5_AMM_PRT_CMDS=1`, `_EXTRA_CMDS=1` (and `=0` for three deleted words) |
| "BC5 Astro (0412 events cap)", "BC5 emulator", "BC5 emulator (lean)" | their launchers | none found |

On D the rejected words of both shortcuts do nothing (their options are gone), without touching the shortcuts.
The fast9 script also (a) rewrites the launcher's `BC5_DIRECT_LEARNED` line and stops when the line is absent, and
(b) checks that the binary holds the text `BC5_GUARD_LEARN_LOG`; so the new `play-pkg.sh` breaks fast9 until its
script is changed. There are five shortcuts for two titles; the standing rule is one per title.

### 6. UNDECIDED: `undecided-list.md`, 62 words, no code change

What is missing, by group: never run on the box or never alone (37, among them the 22 batch-2 library ports: one
start arm, never in play); measured without a conclusion (18: `ARGS_WB`, `ARGS_COPY`, `FORCE_START_000`,
`FL_SERIAL`, the pin cap, `AMM_SCATTER`, `SEMA_TARGETED_WAKE`, `EVENT_COALESCE_SAME`, `MAP_RECORDS=views`); state
unknown on one ring (`CROSS_RING_WAITS`, `RING_DEPS`, `TWO_RING_WAIT_MS`: on daily, never traced whether they still
act); and the promotions that wait for an ASTRO BOT run (14 direct-path words, now in the title's table).

### 7. The rule for the future (proposals, not applied)

`CLAUDE-md-0419.diff` (a line for "How to work") and a paragraph for LESSONS.md, both in this directory: every
experiment ends with a disposition for each switch it added (promote / remove the option / diagnostic / delete /
no verdict, with what is missing).

### 8. Candidate E: the form aimed at the swap (prepared, not compiled)

The top session's order of 2026-11-13: fold exp 0412's K1r into the cleanup candidate, all off by default, the
backend archive as a separate named step. E = B + exp 0412's chain WITHOUT the probe (its "form 2": `mkk1r`, `mkwa`,
`mkcv`, `mkk1f`, `mkkl`; unit 2f4a3d63; a deliberate GPU fault has no place in a build he plays) + this experiment's
three generators (every anchor matched on that unit; one line of K1r's refusal loses its zero-skip half) + exp 0417's
save-data-memory switches and its transferring-mount fix. Patch **d28dff94**, unit c92f5913, `libSaveData.cpp`
164c0869 (`tree-candidate-E-d28dff94.md5`; the patch is in the sessions' notes folder). exp 0412 checked the unit:
its three rule bodies are in it verbatim, and its chain also applies to D's unit.

E needs exp 0412's two backend files (`direct.hpp` 26519fcc, `direct.cpp` b1d27875), so its private build makes a
private backend archive (`mkkit0419e.py` -> `p0419e.sh`) and a swap of E changes the SHARED archive: that step is the
top session's to put to the maintainer. If the archive must wait, D is the form without it.

Private chain `chk0419e.sh` (`mkchk0419e.py`): ASTRO BOT on a fresh directory (the title table must not speak);
the kept bad save with the transferring-mount fix off (the fault) and on (must pass); the second title's walk and
cutscene arm with every new switch off (the control "all off = B"; each prints the title table's line); lean.
K1r ON is exp 0412's own chain. Not covered: the new launchers (the private runner starts exp 0412's own launcher,
which sets the words itself, so the table's "taken" path is exercised only for words that launcher lacks).

### 9. After the maintainer's play on K1r (2026-11-13, "Przerywnik poszedł dalej. Był płynny. […] Pozbądź się zbędnych przełączników"): the options of the defaults go too; E's final form

`mkhard0419.py`, in one place (`Apply()` of `src/bc5/switch_defaults.hpp`, at process start, before any read):

| What | How | Words |
|---|---|---|
| the fixes and the long-standing defaults | forced (`setenv` with overwrite): the environment cannot change them | 35: the 5 of `kFixes`, 30 of `kDefaults` |
| defaults that live at the read site | removed from the environment (`kIgnored`): the read always sees "unset" | 12: `BC5_FAULT_RECORD` (a GPU fault always ends the game with a record), `BC5_DIRECT_COMPUTE_RING`, `_IB_MAX_DW`, `_PREFIX_ALL`, `_SOFT_WAIT_MS`, `KYTY_BC5_AMM_SETBUFFER_GUARD`, `_APR_READAHEAD`, `_APR_SYNC`, `_AT9_VIBRATION`, `_NP_SESSION_V2`, `_PAD_PW_PROPS`, `_PAD_RUMBLE_FALLBACK` |
| `KYTY_BC5_SWITCH_DEFAULTS` | gone (ignored); a control is a build of the older patch | 1 |
| defaults that keep their option (`kSoft`) | `setenv` without overwrite | `BC5_DIRECT_JOURNAL_QUIET` (a launcher may ask for the full journal), `BC5_DIRECT_CHAIN`, `BC5_GC_MODE` |

That is 48 of the inventory's 52 HARDEN rows. The other four are not behaviour defaults and stay: `JOURNAL_QUIET`
(diagnostic) and `KYTY_BC5_NO_PAD_AUDIO`, `_PAD_SPEAKER`, `_PAUSE_ON_BACKGROUND` (the user's configuration). As with
the deletes this is phase 1: the read sites and the old-path code behind them are still in the source and nothing can
reach them; removing that code is the next patch change. Checked before forcing: no launcher, shortcut or script of
experiments 0412-0418 sets one of these to another value, except closed test scripts that asked for the old path
(`KYTY_BC5_APR_POSIX=0`, `_SWITCH_DEFAULTS=0`, `_AMM_SETBUFFER_GUARD=0`, `_FW_NET=0`, `_NP_SESSION_V2=0`,
`_PHYSMAP_SORTED=verify`): on E those words do nothing, so such a control must be a build of B.
`test0419defs.cpp` covers it (forced, ignored, soft, no word in two tables): all ok.

**Candidate E, final form: patch 410273ca** (`tree-candidate-E-410273ca.md5`), unit 449878ca, `switch_defaults.hpp`
2121d020; not compiled. It is made from exp 0412's FORM 4 (unit 9a54eaa4, its branch at 0e2c7e56; this replaces the
form-2 fold of section 8): `BC5_GUARD_K1R` and `BC5_GUARD_K1_FILTER` are on unless "0" at their own read sites (one rule
for both titles; "0" and the filter's "log" stay as the catcher), the switches of its two rules (cover, written scan)
are gone, `BC5_GUARD_WATCH` and `_K1_STAT` are diagnostics, `_LAZY_BY_DATA` has no verdict (off), and `BC5_GUARD_K1R_REPLACE` is gone with `map_shared_over` in the backend (the top
session's order). The backend files are `direct.hpp` e96e5c73 and `direct.cpp` 28100ce5.

**The count.** The inventory had 266 names.

| After E | n | |
|---|---|---|
| can no longer be set: deleted (refuted, superseded, answered) | 29 | 23 of the inventory's DELETE rows, exp 0415's 5 tuning words, and `BC5_DIRECT_LEARNED` (a launcher line read by nothing) |
| can no longer be set: hardened (the tested behaviour, always) | 48 | above |
| **still a word** | **189** | |
| - diagnostics, traces, catchers, test hooks | 69 | off by default; with `BC5_DIRECT_ZERO_NAMES`, which exp 0412's log-only zero scan reads (only the skip's own reader of it is a constant) |
| - no verdict | 63 | `undecided-list.md` + `KYTY_BC5_ANON_SYNC`, `BC5_GUARD_FORGET`, `BC5_GUARD_MAP_RULE`, `BC5_DIRECT_SPI_REQ_CTRL_PS`, `BC5_R3_SUBMIT_EOP_EVENT`, less exp 0415's four |
| - one title's words, now in the code's table for that title or its data in the launcher | 42 | the inventory's 28 title-specific + 13 fixes with no ASTRO BOT run + `BC5_GUARD_LEARN_LOG` |
| - configuration (paths, lists, user settings) | 13 | |
| - general defaults that keep an option | 2 | `BC5_DIRECT_CHAIN`, `BC5_GC_MODE` |

E adds 9 new words: exp 0412's K1r set (4: `BC5_GUARD_K1R` and `_K1_FILTER` on by default, `_WATCH`, `_LAZY_BY_DATA`
off), exp 0417's save words (4, off) and `KYTY_BC5_TITLE_DEFAULTS`. So a build of E reads 198 names, of which 77 fewer than today can change its behaviour
by accident. The next reductions are in the 63 without a verdict (each needs one run) and the 42 title words
(each needs a run on ASTRO BOT to become general and then lose its option).

## Decisions for the maintainer

One "yes" covers the swap of E as a whole (the top session asks): both shared builds, the shared backend archive
(exp 0412's two files), the launchers without the moved words (`play-pkg-0419.diff`, `play-astro-0419.diff`), and the
desktop: one shortcut per title ("BC5 emulator" / "(lean)" through `play-any.sh`); "e10 menu", "0412 K1r test" and
"Astro (0412 events cap)" carry words that E forces, ignores or has removed, so they become plain duplicates and go
to the trash directory. Still his to say separately, because they are behaviour and not housekeeping:

1. `BC5_GUARD_FORGET=10`, `BC5_DIRECT_LAZY_RELEASE=30,eager` + `BC5_GUARD_SPLIT=1`: in the title's table as today; each
   needs one arm without it (exp 0412) before it is hardened or dropped.
2. `BC5_DIRECT_SHADOW_LABELS`' reading rule (the backend) can ride on the archive change of this swap; it is not in E.
3. E changes one line of `audio.cpp` (the reading rule of `KYTY_BC5_NO_PAD_AUDIO`), so by the rule of 2026-11-13 the
   swap of E calls for one replug check; taking that line out of E avoids it.

## Verdict

**Prepared, not built: candidate E (patch 410273ca) = B + exp 0412's K1r (default on, no probe, form 4) + the cleanup + exp
0417's save fix. Of the 266 names, 77 can no longer be set (29 deleted, 48 hardened), 189 remain: 69 diagnostics,
63 without a verdict, 42 one title's, 13 configuration, 2 general defaults with an option.** 47 launcher words moved
into the code (2 general, 45 for the second title) and 15 words got the one reading rule. Every generator's anchors
matched and the laptop tests pass; the first compile is the private build on the box (`p0419e.sh`), then
`chk0419e.sh` on both titles, then the swap on the maintainer's one "yes". The removal of the dead code behind the
77 words is the patch change after that.
