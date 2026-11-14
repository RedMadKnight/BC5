# Experiment 0419: the ONE test build T (patch fec3d656), put together on the laptop on 2026-11-14, NOT built

Ordered by the top session (the rule "all fixes and catchers first, each behind its switch, then test"). Private paths
only; nothing shared is replaced. With every switch below unset, T behaves as candidate G.

| Piece | Value |
|---|---|
| patch 0001 (against KytyPlus f266548) | `fec3d656` (`0001-new23.patch`), 133 patched files |
| main unit `src/libs/bc5LleAgc.cpp` | `c8c5d5ce` (G: 8a930481; `7cb02bac` before step h) |
| `src/kernel/memory.cpp` | `afc69dfe` (G and F: f51c803e) |
| backend | as G: `direct.cpp` aeec4c09, `direct.hpp` e96e5c73 |
| tree list | `tree-test-build-T-fec3d656.md5` |
| kit | shared notes folder, `exp0419-test-build-T/` (`p0419t.sh`, both patches, both tree lists, the backend files, `G-to-T.diff`) |
| build | on the box, in this experiment's slot: `P_NEW23=fec3d656 bash p0419t.sh` (F's private tree d9af28ca must be in place) |

## What is in it, in the order applied

| # | Part | From | Switch (all default off) | State before this build |
|---|---|---|---|---|
| 1 | candidate G: the library ports built in, 48 words gone | this experiment, `candidate-G.md` | none (it is the base) | never compiled |
| 2 | the AJM trail and wider guest-fault dump | `ajm/mkajm0419.py` | `KYTY_BC5_AUDIO_TRAIL=1` | never compiled (`ajm.cpp`, the handler) |
| 3 | AJM jobs run at the batch start | same | `KYTY_BC5_AJM_DEFER=1` | never compiled |
| 4 | AJM live instance ids kept | same | `KYTY_BC5_AJM_LIVE_IDS=1` | never compiled |
| 5 | bd412 / wc412 | exp 0412 `mkbd0412.py` | `BC5_GUARD_BYDATA_NAMES=<heap,...>`; `BC5_GUARD_WRITERS=2` | ran in 16 walks on b413a916 (base F) |
| 6 | kc412 | `mkkc0412.py unit` | `BC5_GUARD_COVER_LOG=1` | ran, as 5 |
| 7 | ph412 | `mkph0412.py` | `BC5_FAULT_POINTERS=1` | ran, as 5 |
| 8 | tl412, dc412 | `mkdw0412.py` | `BC5_TIMEOUT_LAYOUT=1`, `BC5_DISPATCH_COUNT=1` | ran, as 5 |
| 9 | dt412: descriptor targets imported before the submit (the gap of arm b1) | `mkdt0412.py` | `BC5_GUARD_DESC_TARGETS=1` (import), `=2` (log only) | laptop syntax check only |
| 10 | the arming line of the memory first-failure catcher | `mkkc0412.py memory` | `KYTY_BC5_MEM_FIRSTFAIL=1` (exists) | ran, as 5 |
| 12 | two live timing words become the constants they always had: `BC5_DIRECT_CHAIN_HOLD_US` (2 ms), `BC5_DIRECT_DCB_WAIT_MS` (8 ms); the top session's decision of 2026-11-14 | `mkg0419_h.py` | none (the words are gone) | never compiled; behaviour unchanged, both were unset everywhere |
| 13 | the guardian's verdicts (exp 0412 section 95): `BC5_DIRECT_LAZY_RELEASE=30,eager` and `BC5_GUARD_SPLIT=1` are forced rows of the second title (unset at start, set by the title's row with overwrite; another title runs without them, as today); `BC5_GUARD_FORGET` is out (row gone, unset at start; its code is dead until phase 2) | `mkg0419_i.py` | none | CPU test `test0419diag.cpp` all ok; `switch_defaults.hpp` only |
| 11 | a diagnostic: one forced default left unapplied (for the arm without `KYTY_BC5_APR_POSIX=direct`) | `mkdiag0419.py` | `KYTY_BC5_DIAG_UNFORCE=<NAME>[,...]` | CPU test `test0419diag.cpp` all ok; never compiled in the host |

Steps 5 to 10 are exp 0412's generators (branch `exp/0412-memory-guardian`, commit 656e703d), run unchanged on G's
files in the guardian's order 1, 2, 3, 4, 6 on the unit and 5 on `memory.cpp`.

## Checked on the laptop

- No generator of exp 0412 refused on G: every anchor matched once.
- The guardian's change to the unit on G is line for line its change on F: the same 751 changed lines (`diff` of
  G's unit before and after against F's before and after; on F the chain gives its pinned a53e98b7 and c68a3cc4).
- Braces and `#if/#endif` balance in the unit; no name is left defined and unused that F does not have; none of
  the names G deleted occurs in the added lines.
- The dry run of the box step on a clean tree at F (`git apply -R 0001-new18`, `git apply 0001-new23`): 133 of 133
  files match the tree list. `grep -c 'exp 0372'` = 5. `bash -n p0419t.sh`.
- Words: T reads 207 (`words-test-build-T.txt`), **157** can be set after step i (160 before it): G's 202 and 155, plus the guardian's six switches and `KYTY_BC5_DIAG_UNFORCE`, less the two timing words. `switch_defaults.hpp` is 1e881727.

## NOT checked

- Any compile of the unit, `ajm.cpp`, `memory.cpp`, the handler or the backend, the link, any run: `p0419t.sh` is
  the first compile of all of it, so compile errors are an expected kind of result, most likely in G's cuts or the
  AJM block's surroundings.
- Exp 0412's CPU tests against T's unit. G's step e changed code inside the block those tests compile (the parser no
  longer reads `BC5_GUARD_MAP_RULE`, `_PRT_BG`, `_MLOCK`, the cap words), so a test that sets those words is expected
  to differ; the guardian has the unit (`exp0419-test-build-T/unit-bc5LleAgc.cpp`) and is asked to run them.
  **The guardian's answer (2026-11-14, its report, not repeated here):** all 14 of its CPU tests pass against the
  pure blocks taken out of T's unit as it was before step h (7cb02bac; step h changes two lines outside those blocks) (laptop, VS clang++ `-O1 -Wall -Wextra -Werror`); twelve blocks are the
  same as in its own unit, three differ through G's cuts (the guard's `Cfg` reader, `mr412`, `rl412`) and their
  tests still pass (72 of 72, 15,281 of 15,281, 4,970 of 4,970). Its limit: no test sets those environment words, so
  the three changed one-line readers are covered by no test; twelve of its tags are not in the unit and were not
  checked.
- `p0419t.sh` is `p0419g.sh`'s text with the new pins; its messages still say "candidate G". Its list of words the
  binaries must hold does not include the nine new switches: read them with `strings` after the build.

## The slot's order (after the top session's "boks Twoj")

1. `p0419t.sh`: tree, backend archive, normal and lean builds; fix compile errors in the generators, not in the tree.
2. Phase 2 of the dead code with the compiler at hand (`candidate-G.md`, the list), one step at a time, each
   compiled; only what compiles and passes the acceptance stays in T.
3. Private acceptance, RT on: menu; the cutscene arm to G+320; ASTRO BOT x3 with one start on the bad save; the
   lean build; `strings` word list. All switches unset first (T = G); then the night series of `night-series-T.md`; before it one walk with the catchers armed
   (`KYTY_BC5_AUDIO_TRAIL=1` and exp 0412's log-only set), where the AJM create-rate line answers the id-wrap
   candidate.

## Built and accepted (2026-11-14 13:41 to 14:12, the box, this experiment's slot)

T as built is patch `fec3d656` (the header's patch plus steps h and i; unit `c8c5d5ce`, `switch_defaults.hpp` 1e881727).
Raw: `raw/chk0419t.out` (the acceptance, then the build's output).

**Build** (`P_NEW23=fec3d656 bash p0419t.sh`, CPU only): the private tree's 133 patched files match the laptop's; the
private backend's tests 121 of 121; **it compiled at the first attempt**, normal `b0abc471`, lean `b19b3e74`; the
script's word and NID checks pass; the shared archive is untouched (75e30335). 284 warnings in each build, not
compared with F's count; one is in this experiment's new dump code (`runtimeLinker.cpp`, a `%lx` format given an
`unsigned long long`, same size on this machine), left as it is for the night. Copies of both binaries, their md5s
and their word lists: `~/bc5-work/exp0419/bin-T/` on the box.

**Acceptance** (`chk0419t.sh`, one lock line, every new switch unset, RT on, no pad key):

| Run | Result |
|---|---|
| t0a, t0b, t0c: ASTRO BOT 120 s from a fresh save directory | PASS three times, 0 kernel lines, 0 crash lines; the title table does not speak; exp 0418's start-state rows on |
| t0f: ASTRO BOT 30 s on the kept bad save (with `KYTY_BC5_SAVEDATA_TRANSFER_FIX=1`, as in F's acceptance) | PASS |
| t1a: the second title, menu, load, walk to G+240 | clean: 25.7 flips/s over 356 s, longest gap 796 ms, 0 kernel lines, 0 crash lines, 0 would-learn, no fault record; lowest available 436 MiB, GTT 11,755 MiB at 104 s |
| t2cuta: the cutscene arm, 320 s without input | clean to G+320: 29.8 flips/s, longest gap 616 ms, 0 kernel lines; lowest available 839 MiB |
| t3l: the lean build 120 s | PASS, 0 kernel lines, 0 crash lines |

Memory figures are NOT comparable with today's earlier runs: Plasma's on-screen keyboard was off on the desktop
(the guardian's test of 13:38), which lowers the desktop's GTT by about 43 MiB.

Read in the logs: the title table says "38 title defaults, 3 taken, 35 already set in the environment" (the private
launcher still carries the words); the journal of the second title says "lazy release ... on (30 s, eager)" and
"chains ... for up to 2000 us" (steps i and h); ASTRO BOT's journal says "lazy release: off" as before (the forced
rows are the second title's); the three AJM switches print "off".

**Words, final for T.** From the source: 207 read, **157 can be set** (36 rows of one title, 3 general defaults with
an option, 118 other: diagnostics, catchers, the nine new switches). From the binaries (`strings`, the source list
checked against them): the normal build holds 201 of the 207 (absent: the set-buffer test hook's two words and four
of the reset-label and learn diagnostics, compiled out by their gates), the lean build 195. The shared build B
reads 264 and all can be set.

**Without a verdict: 6**, none of them touched by this build. Proposals, one line each, for the top session to rule
as it did for the timing words (the goal is 0):

| Word | Proposal |
|---|---|
| `BC5_DIRECT_MAX_BO_MIB` | delete: its owner's own rule (`owners-verdicts.md`) was "one pair unset against 16, or delete in the candidate after next"; the pair was not run |
| `KYTY_BC5_AMM_SCATTER` | keep as a named opt-in of exp 0412's memory-wall plan (it acts only below 13,824 MiB): verdict "diagnostic, off" |
| `KYTY_BC5_AMM_SETBUFFER_MAP` | keep as an opt-in until a title makes the call with real arguments: verdict "diagnostic, off" |
| `KYTY_BC5_ANON_SYNC` | verdict "diagnostic" for `verify`; the `thread` form is not a fix (its owner: never promote) and can be cut in phase 2 |
| `BC5_R3_SUBMIT_EOP_EVENT` | delete: the route never reaches its path and no scene is known that does |
| `KYTY_BC5_PAD_TOUCH` | the maintainer's own test word (his finger on the pad): his to keep or drop |

**NOT done: phase 2 of the dead code.** The 20 "option removed" markers are the ends of about a dozen features woven
through the unit (the acb CS prefix, acb inherit, the sampler, the VMA fast path, ...); even the three smallest
(`KYTY_BC5_LOAD_DELAY`, `_MIN_FLIP_RATE`, `_MEMORY_FROM_PARAM`) have callers to follow. Every cut changes the binary
and needs a compile and the acceptance again (about 35 minutes a round) just before the night series, and the dead
code blocks nothing: the build passed with it. It is left as a task of its own after the series, with this binary as
the reference.
