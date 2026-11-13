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

## Decisions for the maintainer

1. D removes the recovery words and `alias_learn`. With `BC5_FAULT_RECORD=0` a GPU fault then goes on with no label
   replay and no learned alias. Should `BC5_FAULT_RECORD` lose its `=0` too (a fault always ends the game with a record)?
2. The fast9 and e10 shortcuts: change or retire them (they carry rejected words, and fast9 breaks with the new
   launcher)? One shortcut per title would leave two.
3. Install the new launchers together with D, or keep the old ones for one more round (they work on D)?
4. `BC5_DIRECT_SHADOW_LABELS`' reading rule needs a change of the shared backend archive: with D, or later.
5. `BC5_GUARD_FORGET` (kept), `BC5_GUARD_MAP_RULE` / `_PRT_BG` (kept, off), `BC5_DIRECT_SPI_REQ_CTRL_PS` (kept): each
   waits for one run or for its owner.

## Verdict

**Prepared, not built: candidate D (patch a4d49749) removes the option of 29 words, moves 47 launcher words into the
code (2 general, 45 for the second title) and gives 15 words the one reading rule; the launchers without those words
are made and not installed.** The generators' anchors all matched and the two laptop tests pass; the first compile
is the private build on the box, then both titles (the title's table must show its line for the second title and no
line for ASTRO BOT), then a play by the maintainer before any swap. 52 options wait for the swap after that; 62
words have no verdict.
