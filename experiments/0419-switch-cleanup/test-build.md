# Experiment 0419: the ONE test build T (patch 5f2df896), put together on the laptop on 2026-11-14, NOT built

Ordered by the top session (the rule "all fixes and catchers first, each behind its switch, then test"). Private paths
only; nothing shared is replaced. With every switch below unset, T behaves as candidate G.

| Piece | Value |
|---|---|
| patch 0001 (against KytyPlus f266548) | `5f2df896` (`0001-new23.patch`), 133 patched files |
| main unit `src/libs/bc5LleAgc.cpp` | `7cb02bac` (G: 8a930481) |
| `src/kernel/memory.cpp` | `afc69dfe` (G and F: f51c803e) |
| backend | as G: `direct.cpp` aeec4c09, `direct.hpp` e96e5c73 |
| tree list | `tree-test-build-T-5f2df896.md5` |
| kit | shared notes folder, `exp0419-test-build-T/` (`p0419t.sh`, both patches, both tree lists, the backend files, `G-to-T.diff`) |
| build | on the box, in this experiment's slot: `P_NEW23=5f2df896 bash p0419t.sh` (F's private tree d9af28ca must be in place) |

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
- Words: T reads 209 (G 202): the guardian's six switches and `KYTY_BC5_DIAG_UNFORCE`. `switch_defaults.hpp` is 01398100.

## NOT checked

- Any compile of the unit, `ajm.cpp`, `memory.cpp`, the handler or the backend, the link, any run: `p0419t.sh` is
  the first compile of all of it, so compile errors are an expected kind of result, most likely in G's cuts or the
  AJM block's surroundings.
- Exp 0412's CPU tests against T's unit. G's step e changed code inside the block those tests compile (the parser no
  longer reads `BC5_GUARD_MAP_RULE`, `_PRT_BG`, `_MLOCK`, the cap words), so a test that sets those words is expected
  to differ; the guardian has the unit (`exp0419-test-build-T/unit-bc5LleAgc.cpp`) and is asked to run them.
  **The guardian's answer (2026-11-14, its report, not repeated here):** all 14 of its CPU tests pass against the
  pure blocks taken out of T's unit 7cb02bac (laptop, VS clang++ `-O1 -Wall -Wextra -Werror`); twelve blocks are the
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
