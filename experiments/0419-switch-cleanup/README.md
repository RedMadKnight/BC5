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

### 10. Candidate E built and run privately (2026-11-13 18:28-19:12)

`p0419e.sh` (tree 1689b7da -> 410273ca, a private backend archive from exp 0412's two files): the private archive
is d4c4882e, normal **93188758**, lean **96a995c2**; the shared tree, archive and builds were only read. First
compile of the whole of E: no error (the normal build's log has 286 warnings, not compared with B's).
`chk0419e.sh` (`raw/chk0419e.out`), no pad key in any run, 13.2 GB available before it, no browser on the box:

| Arm | What | Result |
|---|---|---|
| k0a | ASTRO BOT 120 s, fresh directory, E's defaults (K1R and its filter on) | PASS, kernel 0, crash 0; the title table is silent (no line), as it must be |
| k0x | ASTRO BOT on the kept bad save, the fix off | ends by itself at 5 s: the fault of exp 0417 section 15, as expected |
| k0f | the same, `KYTY_BC5_SAVEDATA_TRANSFER_FIX=1` | **PASS 30 s**; "sdt417: transferring mount of PPSA01325/sce_sdmemory: no such save, NOT_FOUND (nothing created)" |
| k1 | the second title's walk to G+240, E's defaults | clean; 25.5 flips/s, 67 s with a gap over 100 ms, longest 1238 ms; available 930 / 845 MiB at ~60 / ~104 s |
| k1off | the same, `BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0` | clean; 26.1 flips/s, 61 s, longest 638 ms; 948 / 860 MiB |
| k2cut | the cutscene arm to its end (320 s after gameplay, no input) | clean to G+320, 28.9 flips/s, longest gap 1357 ms, no fault, no record; K1r's last line: 406 read-only zero pieces cover 808 MiB of never-written memory |
| k3l | lean 120 s | PASS |
| k4wall | the walk to G+560 with exp 0412's log-only zero scan (frame numbers not comparable) | clean to G+560; 88 "zero scan" lines, all five scans ran; the whole-box table and the fdinfo read are on the box for exp 0412 |

Every second-title arm printed "title PPSA03671: 45 title defaults, 1 taken, 44 already set in the environment":
the title is found from the command line, and the private runner's launcher (exp 0412's) sets 44 of the 45 itself,
so the table's "taken" path ran for one word only. The new launchers are what exercises it in full.

Against B on the same route today (exp 0417: 25.7-26.3 flips/s, longest gap 574-701 ms): the flip rate is the same;
**the longest gap is about twice as long in the two arms with K1r on (1238, 1357 ms) and not in the arm with it off
(638 ms)**. One run each, so not a finding; put to exp 0412. The maintainer's own play on K1r was "smooth".

Not done here: the "taken" path of the title table with the new launchers; a play; the swap.

### 11. The swap script for E, dry-run (prepared, not run on the box)

`mkswap0419e.py` -> `int0419e.sh`: the tree 27b6416f -> 410273ca, exp 0412's two backend files into the shared backend
source, the shared archive rebuilt (75e30335 -> d4c4882e expected, as the private build gave), both shared builds.
Kept first and read back: both binaries, the archive (twice) and the two source files; a failure restores all of
them and the tree and checks the restore. Its kit: `0001-new14.patch`, `0001-new17.patch`, `tree17.md5`,
`backend-direct.hpp` (e96e5c73), `backend-direct.cpp` (28100ce5).

`dryswap0419e.sh` on the laptop with stand-ins (`raw/dryswap0419e.out`): **40 of 40 checks in four cases**: the swap
as expected (tree, archive, backend files, copies, "byte-identical to the private builds", lock released); the
backend build fails; the rebuilt archive is not the expected one; the lean emulator build fails after the archive
and the normal binary have changed. In each of the three failures the two source files, the archive, both binaries
and the tree read back as before and the lock is released. Not covered by a dry run: the real builds, the real
archive's sum, and whether the shared binaries equal the private ones (for B they did not).

### 12. E is not swapped; candidate F built and accepted privately (2026-11-13 19:25-20:21)

Exp 0412 traced E's long gaps (section 10) to its own code: `k1r412::cover()` walked the imported-buffer list from its
start for each of some 21,000 views, 19-20 ms per full sync in the "want" step against 0.8 ms with K1r off, and a
1.0-1.36 s stall in the menu at about 39 s in two of three arms. E is therefore withdrawn. By the top session's order
one candidate carries all the fixes:

**F = B + exp 0412's FORM 6** (the cover pass with a binary search; its writers catcher `BC5_GUARD_WRITERS`, off)
**+ this experiment's cleanup + exp 0417's save fix + exp 0418's start-state table** (`0418-on-410273ca.diff`: always on,
its three words read by nothing, the second title's table at 42 rows). Patch **d9af28ca**, unit 59d17cf5,
`switch_defaults.hpp` 6fbfb8a5 (`tree-candidate-F-d9af28ca.md5`, 132 files); backend files as E's (e96e5c73, 28100ce5).
Every generator anchor matched on form 6 and exp 0418's diff applied cleanly on top. `test0419defs.cpp` (42 rows) and
`cmplaunch0419.py` (43 launcher words in the tables, 0 problems) pass; the launcher diff also drops exp 0418's three
words. Phase 2 of the deletes (removing the dead code) is NOT in F: not ready, and not to be rushed into a unit two
other sessions changed the same evening.

Private build (`p0419f.sh`): normal **1a2900a0**, lean **034bf107**, the private archive d4c4882e as before; both
binaries kept under `~/bc5-work/exp0413/kept/`. Chain `chk0419f.sh` (`raw/fchain.out`), no pad key in any run, 13.2 GB
available before it:

| Run | K1r | Flips/s | s with a gap > 100 ms | Longest gap | End |
|---|---|---|---|---|---|
| ASTRO BOT 120 s x3 (fresh directory) | on | - | - | - | PASS x3, kernel 0, crash 0; the title table silent; exp 0418's line "rows on: ... (8 rows); skipped: none" |
| ASTRO BOT on the kept bad save, the transfer fix on | on | - | - | - | PASS 30 s, "NOT_FOUND (nothing created)" |
| m1a walk | on | 25.6 | 60 | 698 ms | G+240, clean |
| m1b walk | on | 25.4 | 74 | 695 ms | G+240, clean |
| m1offa walk | off (+ filter off) | 25.4 | 76 | 879 ms | G+240, clean |
| m1offb walk | off (+ filter off) | 25.7 | 54 | 625 ms | G+240, clean |
| m2cuta cutscene arm 320 s | on | 29.8 | 40 | 408 ms | G+320, clean, no fault record |
| m2cutb cutscene arm 320 s | on | 29.5 | 35 | 678 ms | G+320, clean, no fault record |
| lean 120 s | on | - | - | - | PASS |

**The stall is gone: with K1r on the longest gap is 408-698 ms in four runs (E: 1238 and 1357 ms), the same as with it
off (625, 879 ms) and as B today (574-701 ms).** The frame-profile lines over 500 ms are 0-4 per run and all sit at
92-155 s (the load and just after it); none is in the menu at 39 s. The 1.1 s gap "outside the host" of E's k1 at
249 s did not come back in these six runs. The "want" step is exp 0412's to read from the journals (the chain prints
each run's last timing-split line; m1a's has 3.4 ms over 4 full syncs). Every second-title run printed the title
table's line ("42 title defaults, 1 taken, 41 already set") and exp 0418's start-state line.

The runners' kernel stopper was fixed first (`fixstop0419.py`, LESSONS R54): it no longer takes a backtrace frame
such as `amdgpu_gem_fault+0x95/0x100` for a GPU fault.

**Exp 0412's mark, read from the six journals (`want0419.sh`): "want" under 2 ms per full sync with K1r on is NOT
met at the maxima.** Per timing-split line with a full sync, want / full:

| Run | K1r | Lines with a full sync | Over 2 ms | The three largest (ms per full sync, at t) |
|---|---|---|---|---|
| m1a | on | 1,905 | 64 | 3.10 (63 s), 3.00 (52 s), 2.90 (66 s) |
| m1b | on | 1,955 | 103 | 3.30 (51 s), 3.20 (56 s), 3.15 (49 s) |
| m2cuta | on | 2,612 | 29 | 3.10 (51 s), 3.10 (46 s), 3.00 (51 s) |
| m2cutb | on | 2,444 | 48 | 2.90 (68 s), 2.80 (46 s), 2.75 (45 s) |
| m1offa | off | 1,911 | 0 | 1.50 (336 s), 1.20, 1.10 |
| m1offb | off | 2,013 | 0 | 1.40 (88 s), 1.20, 1.20 |

With K1r on the worst full syncs cost about 3 ms, all between 45 and 68 s (the menu), in 1-5 % of the windows;
with it off the worst is 1.5 ms. E measured 18.8-20.3 ms. No long gap came with them. Whether 3 ms at the menu's
worst is acceptable against the 2 ms mark is exp 0412's and the top session's decision.

After the acceptance, under one lock line (`rchain.sh`; results in section 13): exp 0412's extra wall walk with its
writers catcher, and a private diagnostic build with exp 0418's one-off RSRC2 journal; the private builds go back to F.

### 13. After the acceptance: a GPU hang in the long walk on F; exp 0418's RSRC2 journal (2026-11-13 20:22-20:54)

`rchain.sh` (`raw/rchain.out`), one lock line, F's private binary 1a2900a0:

| Step | Result |
|---|---|
| m5wall: the walk to G+560 with exp 0412's zero scan and `BC5_GUARD_WRITERS=1` (outside the acceptance) | **GPU HANG at 601 s** (G+484): `ring gfx_0.0.0 timeout`, no fault address, the ring reset succeeded, the game ended itself with a fault record (`~/bc5-data/captures/faults/20261113-203301`; journal `~/bc5-data/captures/play-20261113-2022/gc/direct.log`; neither committed). Until then 25.8 flips/s, longest gap 674 ms. Four of the five scans ran; the whole-box table and the fdinfo read (due at 615 s) are empty |
| a private diagnostic build, F + exp 0418's `rsrc2_journal` (patch e794fbe6, unit 877d6edc) | builds |
| r1: the second title's walk with `BC5_DIRECT_RSRC2_JOURNAL=1` | clean to G+240; totals after 188,001 buffers: PS 4,174,715 words, GS 4,453,233, HS 445,361, CS 2,755,281, **TRAP_PRESENT 0, EXCP_EN 0** in every stage |
| r0a: ASTRO BOT 120 s with it | PASS; after 52,001 buffers PS 662,298, GS 1,169,993, HS 82,138, CS 771,515, **0 / 0** |
| back to F | the private builds read 1a2900a0 / 034bf107 again (the same bytes) |

**The hang is a finding against F until shown otherwise.** F's six acceptance runs ended at G+240 or G+320; this is
its only run past that. E's long walk on the same route (k4wall, to G+560, with the scan) was clean to 681 s. What
differs between the two: exp 0412's form 6 for form 4, `BC5_GUARD_WRITERS=1`, and exp 0418's start-state table (always
on in F; it writes `SPI_SHADER_REQ_CTRL_PS`, whose one earlier verdict was a failed play, audit row B2). The journal
shows 409 MiB available and 12,237 of 13,312 MiB of GTT at 420 s. One run: no cause is named here. By the
maintainer's rule it is a bug to remove at its source, with its record. Next: the long walk on F with no scan and no
writers catcher, twice; if it hangs, the same with exp 0418's rows skipped, and on E's kept form. F is NOT ready for
the swap before that.

A mistake of this chain: it did not stop at the hang's kernel lines (the extra arm's status was not checked) and went
on to the diagnostic build and two more runs; both were clean and the box did not reboot.

Exp 0418's answer from its journal: no shader of either title loads an RSRC2 word with TRAP_PRESENT or EXCP_EN on
these routes; `rsrc2_journal` is not kept in the tree. Its start-state line is in both titles' logs with all eight
rows and none skipped; the second title also has the TF ring and HS offchip lines; neither has a GS ring line.

### 14. The deciding series for the hang (2026-11-13 21:00-22:00): not reproduced; a second, different failure

`series0419f.sh` (`raw/series0419f.out`): five walks of the second title to G+620 (past 601 s), a private copy of the
save, the fault record on, RT on, no pad key in any, 13.4 GB available before it. All five ran.

| Arm | Build and words | End | Flips/s | Longest gap | Available / GTT at 600 s |
|---|---|---|---|---|---|
| sA | F, no scan, no writers catcher | **the title faulted on the CPU at 543 s**: a read of address 0x17fc at eboot+0x1b349f (exit 65); kernel lines 0, no GPU fault, no fault record; available 531 MiB at 530 s, the memory watchdog did not act (lowest 487 MiB) | 25.7 | 883 ms | - |
| sB | F, `BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0` | clean to G+620 | 26.3 | 739 ms | 434 MiB / 12,310 |
| sC | F without exp 0418's five new rows | clean to G+620 | 25.9 | 1020 ms | 343 MiB / 12,258 |
| sD | the shared build B (51af1ed7), the control | clean to G+620 | 26.1 | 875 ms | 494 MiB / 12,218 |
| sE | F with the zero scan and `BC5_GUARD_WRITERS=1` (the arm that hung) | clean to G+620 | 24.8 | 573 ms | 425 MiB / 12,289 |

**The GPU hang of 601 s did not come back in five long walks, including the same arm run again (sE).** No arm
isolates a cause: exp 0418's rows, the writers catcher and K1r each have a clean run with them on.

**A second failure, of another kind, in the plain F arm (sA):** the title's own code read a 16-bit value through a
pointer of about zero (`movzx ebx, word [r11 + r10 - 4]` with r11 0x800, r10 0x1000) at eboot+0x1b349f, 543 s in.
That address is in no record of the repository. No GPU fault, no kernel line, memory not at the wall.

So far, long walks past G+320 on this route:

| Build | K1r | Runs | Failed |
|---|---|---|---|
| F | on | 4 (m5wall, sA, sC, sE) | 2: one GPU hang at 601 s, one guest fault at 543 s |
| F | off | 1 (sB) | 0 |
| E (form 4) | on | 1 (k4wall) | 0 |
| B (shared today) | none | 1 (sD) | 0 |

Two failures of four against none of three is NOT a result: the two failures are different faults, and one clean
control says nothing about how often B fails at this length (F403 and F813, hangs of this title, are open in
HANDOFF and come once in several runs). What it does say: **F must not be swapped on these numbers**, and the next
step is counts, not another guess: the same long walk several times on B and on F with K1r on and off (13 minutes of
box time each), stopping to read each fault's record. Both failures are bugs to remove at their source by the
maintainer's rule; neither has a cause yet.

### 15. The second series: nine long walks, none failed (2026-11-13 22:06 to 2026-11-14 00:01)

Ordered by the top session. Nine walks of the second title to G+620, interleaved, no pad key in any (the recorder:
0 presses each), `KYTY_BC5_MEM_FIRSTFAIL=1 KYTY_BC5_TRAP_LOG=1` in every arm (log only), RT on, one lock line.
Script `counts0419f.sh`, raw `raw/counts0419f.out`. Private F is 1a2900a0, the shared build is B's 51af1ed7.

| Arm | Build and words | End | Flips/s | Longest gap | Available / GTT / swap at 600 s (MiB) |
|---|---|---|---|---|---|
| dF1 | F | G+620, clean | 25.2 | 872 ms | 435 / 12,323 / 696 |
| dB1 | shared B | G+620, clean | 25.1 | 795 ms | 536 / 12,252 / 721 |
| dK1 | F, `BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0` | G+620, clean | 25.6 | 739 ms | 497 / 12,272 / 700 |
| dN1 | F without exp 0418's five new rows | G+620, clean | 25.4 | 677 ms | 457 / 12,177 / 658 |
| dF2 | F | G+620, clean | 25.2 | 902 ms | 459 / 12,217 / 699 |
| dB2 | shared B | G+620, clean | 25.6 | 953 ms | 493 / 12,228 / 694 |
| dK2 | F, K1r and its filter off | G+620, clean | 25.3 | 736 ms | 444 / 12,228 / 671 |
| dN2 | F without exp 0418's five new rows | G+620, clean | 25.3 | 531 ms | 456 / 12,216 / 718 |
| dF3 | F | G+620, clean | 25.5 | 608 ms | 556 / 12,225 / 681 |

In all nine: 0 kernel lines, 0 crash lines, 0 fault records (the newest record is still 20261113-203301, the hang of
section 13), 0 would-learn. The trap catcher printed its arming line in every arm (`sigaction(SIGTRAP) rc 0`) and
nothing else; the memory first-failure catcher printed nothing. It has no arming line, so "it was armed" rests on the
word being in F's binary (`grep -c` = 1) and on exp 0412's code, not on a line of these runs. The lowest available
memory in a 580-620 s window was 389 MiB (dN1); GTT stayed between 12,177 and 12,323 of 13,312 MiB. The four variants
do not differ in speed (25.1-25.6 flips/s) or in memory beyond the run-to-run spread.

**Counts of walks past G+320, all runs so far** (sections 12 to 15):

| Variant | Failed / run | The failures |
|---|---|---|
| F, K1r on (defaults, with or without the scan and writers catcher) | 2 / 7 | GPU hang at 601 s (m5wall); guest CPU fault at 543 s (sA) |
| F, K1r and its filter off | 0 / 3 | |
| F without exp 0418's five new rows | 0 / 3 | |
| shared B | 0 / 3 | |
| E | 0 / 1 | |

What this says and does not say: neither fault came back in five more walks on F's defaults, so each is rarer than
the first four runs suggested; 2 of 7 against 0 of 3 does not separate F from B (Fisher's exact test, one-sided:
p = 0.47), nor K1r on from off. Neither fault is explained, and the first-failure catchers have nothing to show
because nothing failed. The hypothesis "a null pointer after a failed memory call near the wall" is neither supported
nor refuted: no arm came near the conditions of sA's fault with the catcher on.

### 16. Candidate G prepared on the laptop (2026-11-14, no box access, nothing built)

Ordered by the top session for the night. `candidate-G.md` is the record: G = F + the library ports built in (22 words
gone), eight words deleted with their code (and the code of three whose options F had removed), one made a constant, twelve more with the option gone and the code still to
cut, in all 43 words; patch `99f32d3b`, unit `dd30a593`, backend `direct.cpp` `9eb378e1`. Counted from the source
(`words0419g.py`, `settable0419g.py`): B reads 264 words, F 247 (200 can be set), G 204 (**157** can be set). Checked:
every edit matched once, braces balance, the library units pass `-fsyntax-only`, the defaults test, a dry run of the
patch swap F -> G on a clean clone (132 of 132 files). NOT checked: any compile of the main unit (Linux-only), the
link, any run: `p0419g.sh` on the box is G's first compile. Five hang-hunt words are kept until the maintainer confirms
their delete knowing that F403 and F813 are open; `dla-maintainera-slowa.md` (Polish) is the word-by-word sheet for him.
F and G still change three lines of `audio.cpp` (the reading rule of `KYTY_BC5_NO_PAD_AUDIO`), so their swap gets one
software replug check.

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

**Candidate F (patch d9af28ca) is built and passed its acceptance runs on both titles (section 12), but its one run
past G+320 ended in a GPU hang at 601 s (section 13): The deciding series (section 14) did not reproduce the hang in five long walks and
added a different failure (the title faulted on the CPU at 543 s in the plain F arm): 2 of 4 long walks on F with K1r
on failed, 0 of 1 with it off, 0 of 1 on B. F is NOT ready for the swap. The second series (section 15) ran nine more long walks (F x3, F K1r off x2, F without exp 0418's rows x2, B x2) and none failed: 2 of 7 on F's defaults in all, 0 of 3 on each other variant, which does not separate F from B. Both faults stay unexplained; whether F is swapped with two rare, unexplained faults on record is the maintainer's decision. Nothing is swapped.**
F = B + exp 0412's K1r (form 6, default on, the cover pass fixed) + the cleanup + exp 0417's save fix + exp 0418's
start-state table. E (410273ca) is withdrawn: its K1r stalled the menu for over a second. Of the inventory's 266
names 77 can no longer be set (29 deleted, 48 hardened) and 189 remain: 69 diagnostics, 63 without a verdict, 42 one
title's, 13 configuration, 2 general defaults with an option; exp 0418's change takes four more of them out (`BC5_DIRECT_CP_COHER_START_DELAY`,
`_SPI_REQ_CTRL_PS`, `_GC_TF_RING`, `_GC_HS_OFFCHIP` are read by nothing in F: 81 gone, 185 remain). The swap script for F is made and dry-run (`mkswap0419f.py` -> `int0419f.sh`,
`dryswap0419f.sh`: 40 of 40, `raw/dryswap0419f.out`). Before the swap: the maintainer's one "yes" (builds, backend archive, launchers, shortcuts), and
his play. The dead code behind the removed options is the patch change after that.
