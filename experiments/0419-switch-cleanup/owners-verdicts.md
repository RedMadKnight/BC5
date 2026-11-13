# Experiment 0419: the owners' verdicts (2026-11-13, by message; nothing re-measured for this)

The inventory's DELETE and PROMOTE rows were put to the sessions that own the words. Their answers override the
inventory. "B" is the shared patch 27b6416f.

## exp 0415 (load times and fps); sections are of `experiments/0415-load-times-fps/README.md`

| Word | Inventory | Owner | Behind it / what is missing |
|---|---|---|---|
| `KYTY_BC5_ANON_SYNC` | DELETE | **UNDECIDED, keep** | `verify` is a diagnostic (708 walks, 0 misses, section 16, F824). `thread` measured the gain (frames over 50 ms 17-25 % -> 9-17 %, two pairs) but is not a fix: a new anonymous mapping can miss the first submission after it. Never promote `thread`. Missing: the `events` form (not built), then verify + A/B + a long play |
| `KYTY_BC5_ANON_SYNC_MS` | DELETE | KEEP-DIAG | the thread's period; goes with the thread form |
| `KYTY_BC5_NAMES_FAST`, `KYTY_BC5_VMA_FAST` | DELETE | DELETE | exact, no effect in 5 runs (section 10). `src/bc5/sync_fast.hpp` and its test go with them (also the dead helper of the removed `KYTY_BC5_WINDOW_FAST`) |
| `KYTY_BC5_RING_SPIN_US`, `KYTY_BC5_TIMERSLACK_NS`, `KYTY_BC5_MUTEX_SPIN_US` | UNDECIDED | DELETE | no effect on the loads at 1-2 s resolution (sections 6, 9); never measured on fps |
| `KYTY_BC5_RING_POLL_US` | UNDECIDED | DELETE the word, keep 200 in the code | 50 and 1000 gave the same loads |
| `KYTY_BC5_LOAD_DELAY` | (KEEP-DIAG) | DELETE | a probe whose answer is in section 6 |
| `KYTY_BC5_APR_POSIX` | HARDEN | HARDEN | default `direct` since 11-13 (sections 5-8, F817); `=0` can go later |
| `KYTY_BC5_MAP_RECORDS` (+ `_CHECK_MS`) | UNDECIDED | `verify` KEEP-DIAG; `views` UNDECIDED | views: correct, no gain as built; missing: the form without the copy and its A/B; not run with K1r |
| `KYTY_BC5_LOAD_STAT`, `KYTY_BC5_FRAME_STAT`, `_FRAME_STAT_WIN` | KEEP-DIAG | KEEP-DIAG | every table of exp 0415 comes from them |
| `KYTY_BC5_APR_READAHEAD`, `_APR_SYNC`, `_APR_PARALLEL` | - | not its words | `READAHEAD=12` gave nothing while the disk was the limit; the other two never run by it |
| `KYTY_BC5_SEMA_TARGETED_WAKE`, `_EVENT_COALESCE_SAME` | UNDECIDED | exp 0416's (this session) | no effect on the loads; written for correctness, so the loads say nothing |

Request: the unit hashes after NAMES_FAST / VMA_FAST / the spin words go (its kits rebase on that text).

## exp 0412 (the memory guardian); "in B" = a getenv in the shared unit 8126c0aa

| Word | Inventory | Owner | Note |
|---|---|---|---|
| `BC5_DIRECT_LEARNED`, `_LEARN_GUEST_ONLY`, `BC5_GUARD_APPLY_MIN_MS` | DELETE | DELETE-ok | the learned path is gone since nl412; APPLY_MIN_MS is still read in B, dead |
| `BC5_GUARD_LEARN_LOG`, `BC5_GUARD_MAP_RULE`, `BC5_GUARD_PRT_BG` | PROMOTE / DELETE / UNDECIDED | "not read in B at all" (only its private builds); DELETE-ok from launchers and words files | to check against the unit; the fast9 shortcut refuses to start when the shared binary lacks the text `BC5_GUARD_LEARN_LOG` |
| `BC5_DIRECT_RESET_LABELS_ADD` | DELETE | DELETE-ok ONLY with the whole recovery path | unreachable while `BC5_FAULT_RECORD` is on by default; if `BC5_FAULT_RECORD=0` must keep working, keep all four recovery words (the other three are exp 0401's) |
| `BC5_DIRECT_ZERO_SKIP`, `_ZERO_NAMES`, `BC5_GUARD_ZSKIP_POLL_SUBMIT` | DELETE | DELETE-ok | its `mkk1r0412.py` reads ZERO_SKIP only to refuse: tell it when the word goes |
| `BC5_GUARD_FILE`, `_FILE_ROOT`, `BC5_GUARD_PSI` | DELETE | DELETE-ok | never moved the wall in any arm |
| `BC5_GUARD_FORGET` | DELETE | **KEEP for now** | in arm fast8's words (FORGET=10), which every cutscene run uses; missing: one fast8 arm without it |
| `BC5_GUARD_SPLIT` + `BC5_DIRECT_LAZY_RELEASE` | UNDECIDED | KEEP, a promote candidate | missing: the maintainer's own play with it |
| `BC5_GUARD_LEDGER`, `BC5_GUARD_K1_STAT` | KEEP-DIAG | KEEP | log-only catchers |
| `BC5_GUARD_PIN_CAP`, `_CAP_ACT`, `_CAP_NAMES`, `BC5_GUARD_MLOCK` | UNDECIDED | undecided | log-only today / no clean measurement |
| `BC5_FAULT_RECORD` (+ the save guard), `BC5_DIRECT_TIMEOUT_PROBE` | - | KEEP | the maintainer's rule for GPU faults |
| the K1r chain (`BC5_GUARD_K1R*`, `_WATCH`, `_K1_FILTER`, `_LAZY_BY_DATA`) | not in B | keep, live, private | its scripts anchor on the text of `direct_sync_one`, the k1r hooks, `covered_sorted` and `direct_lazy_name` in 8126c0aa: the candidate unit goes to it before it goes shared |
| `BC5_DIRECT_HEAP_GUARDS` | UNDECIDED | not its word | exp 0417's (this session): clean with and without; undecided |

## exp 0412, second round (2026-11-13 evening): its line per word for the candidate after F

Checked by it against F's unit 59d17cf5; none of this is the maintainer's word.

| Word | Its line | Detail |
|---|---|---|
| `BC5_GUARD_MLOCK` | DELETE | never in a play; needs `ulimit -l` |
| `BC5_GUARD_PIN_CAP`, `_CAP_ACT`, `_CAP_NAMES` | DELETE | the PIN_CAP half of K1r's "REFUSED" text and its getenv go with it |
| `BC5_GUARD_FORGET` | one arm without, then constant or delete | its reason (264 MiB "forced and under no view" after 5 min) was measured when learned windows still forced chunks. Read on a walk to G+560: the ledger's orphans and GTT at 420 s and 600 s; under 100 MiB difference: delete, otherwise constant 10 |
| `BC5_GUARD_MAP_RULE` + `BC5_GUARD_PRT_BG` | DELETE, confirmed | goes: `mr412::rule()`, `rule_for()` and its use in `direct_sync`, `mr412::prt_bg()`, `in_bg()`, `kBgLo`/`kBgHi`, `g_mr412_bg`, the background branch of `mr412_prt_open`, the `g_mr412_bg && mr412::in_bg` return. STAYS: `mr412_prt_open` itself (the AMM window's PRT mapping), `mr412::classify` (also used by the fault record), `mr412_would_learn` and its call |
| `BC5_DIRECT_LAZY_RELEASE=30,eager` + `BC5_GUARD_SPLIT=1` | one arm without on both titles | CONSTANT if with them the direct pin or GTT at 420 s / 600 s is lower by 100 MiB or more on either title; read the longest gap too (the split runs inside the device mutex); if "without" is no worse by 100 MiB: delete both |
| `BC5_GUARD_LAZY_BY_DATA` | stays off, its own | until its option B's first heap arm is read; then delete or constant in the candidate after that |
| `BC5_DIRECT_MAX_BO_MIB` | stays, its own | until one pair unset against 16 on the walk; not run by the candidate after next: delete |
| `BC5_GUARD_LEARN_LOG` | the word and `mr412::learn_log()` can go | with value 2's behaviour constant (the alias file is never written). Condition: its wrappers grep the binary for the string and refuse to start without it, so the wrapper check and the shortcuts change in the same swap, on the maintainer's own word |
| diagnostics (`_WATCH`, `_K1_STAT`, `_LEDGER`, `_WRITERS`, `ZEROSCAN_AT`, `ZERO_NAMES`, `MEM_FIRSTFAIL`, `TRAP_LOG`, `TIMEOUT_PROBE`) | all stay | except `BC5_DIRECT_ZEROSCAN_OUT`, which can go (its only reader was the zero skip) |

New on its side, private build only: `BC5_GUARD_WRITERS=2` (tag wc412) and `BC5_GUARD_BYDATA_NAMES` (tag bd412), for its
memory-wall arms; not in any candidate.
