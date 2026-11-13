# Experiment 0419: the candidate after F ("G"): every word's disposition, and the count

The maintainer's decisions of 2026-11-13, relayed by the top session, with the owners' lines (`owners-verdicts.md`),
the code reading (`launcher-words.md`) and the records (`undecided-plan.md`, its correction). Nothing here is built.
G is made only when F's two open faults (README sections 13 and 14) are understood: G's base is F.

## Approved by the maintainer

| Disposition | Words | n | Note |
|---|---|---|---|
| DELETE with the code | `KYTY_BC5_SEMA_TARGETED_WAKE`, `_EVENT_COALESCE_SAME`, `BC5_GUARD_MLOCK`, `BC5_DIRECT_TF_DEFAULT`, `BC5_GUARD_MAP_RULE`, `_PRT_BG`, `KYTY_BC5_AMM_PRT_CMDS`, `_AMM_EXTRA_CMDS`, `BC5_GUARD_PIN_CAP`, `_CAP_ACT`, `_CAP_NAMES` | 11 | exp 0412 named what goes with MAP_RULE / PRT_BG and what stays; `TF_DEFAULT`'s block holds the only call of `hs_offchip_force()`: to check against exp 0418's table before it is cut |
| DELETE with the code (already constants in F) | `KYTY_BC5_MUTEX_SPIN_US`, `_RING_SPIN_US`, `_TIMERSLACK_NS` | (3) | their options went in E/F; G removes the code |
| CONSTANT, no option | `KYTY_BC5_RING_POLL_US` = 200 (already in F), `BC5_DIRECT_HEAP_GUARDS` = always on | 1 new | |
| BUILT IN, lazy | the 23 library words: 20 `KYTY_BC5_LOAD_*` of batch 2, `_VOICE_PORTS`, `_NPTUS_FRIENDS_RUN`, `_USBD_ALLOW` | 23 | "wbudowane, ale uruchamiane tylko jeżeli gra będzie wołać": the tables always registered, nothing started before a title's first call; the analysis of what each does at load is being made; proof: both titles, start and walk |
| DELETE, dead on one ring | `BC5_DIRECT_CROSS_RING_WAITS`, `_RING_DEPS`, `_TWO_RING_WAIT_MS` | 3 | `launcher-words.md` |
| ONE ARM, then delete | `BC5_GUARD_FORGET` | 1 | a walk to G+560 without it; exp 0412's mark: under 100 MiB difference in the ledger's orphans and GTT at 420 s and 600 s |
| STAYS | `KYTY_BC5_MAP_RECORDS`, `_MAP_RECORDS_CHECK_MS` | 2 | exp 0415, the base of its next stages |

## Approved, but decided on a premise that was wrong: back to the maintainer first

"Próby z polowania na dawne zawieszenia => usunąć z kodu" (nine words) and `BC5_DIRECT_FL_SERIAL` in the delete list
above. The plan he saw called them tries for hangs that are gone. HANDOFF says F403 and F813 are OPEN, and candidate F
hung the GPU tonight in the way those classes describe (`undecided-plan.md`, "Correction to group E").

| Word | The record | This session's proposal |
|---|---|---|
| `BC5_DIRECT_GPU_CHECK_YZ`, `_GPU_CHECK_ZERO`, `_FORCE_START_000`, `_PIECES_NO_CLEAR`, `_ARGS_COPY` | the records themselves discard them (would not have caught the case; never run; the class hung again with it; would not isolate; "must not be used" alone) | delete, as decided (5) |
| `BC5_DIRECT_ARGS_WB` | one 36.6-minute play without F403; "a second long play ... is the decisive next step", never made | keep until that play or until tonight's hang has a cause |
| `BC5_DIRECT_FL_SERIAL`, `_FL_VGT_FLUSH` | fix candidates for the draw class (F813, open); SERIAL: 0 of 8 against 0 of 10, 3 % slower; VGT_FLUSH never run | keep as that hang's candidate fixes |
| `BC5_DIRECT_ARGS_FLUSH`, `_ARGS_FLUSH_DRAWS` | built, never run on the GPU | keep, the same |

If he confirms the delete of all ten knowing this, all ten go. Seven of them are read in `backend/src/direct.cpp`.

## Still his to decide, word by word (live launcher words)

| Word | State | Choice |
|---|---|---|
| `BC5_DIRECT_CHAIN_HOLD_US` | live at 2 ms, never varied | constant, or one arm at another value first |
| `BC5_DIRECT_DCB_WAIT_MS` | live at 8 ms; F285: at 100 ms 0 give-ups against 13, and 27 s of long frames against 8 | constant 8, or look at 100 again |
| `BC5_DIRECT_LAZY_RELEASE` + `BC5_GUARD_SPLIT` | live every day | one arm without on both titles; exp 0412's mark 100 MiB |

## Stays with an owner and a term

`KYTY_BC5_ANON_SYNC` (exp 0415, until its events form), `BC5_GUARD_LAZY_BY_DATA` (exp 0412, until its first heap arm),
`BC5_DIRECT_MAX_BO_MIB` (exp 0412, one pair; not run by the candidate after next: delete), `KYTY_BC5_AMM_SCATTER`
(exp 0412's wall plan), `KYTY_BC5_AMM_SETBUFFER_MAP` (until a title makes the call), `KYTY_BC5_PAD_TOUCH` (the
maintainer's touch), `BC5_R3_SUBMIT_EOP_EVENT` (promote after one arm on a scene that reaches its path; the walk does not).
With the shortcuts' change in the same swap: `BC5_GUARD_LEARN_LOG` goes; `BC5_DIRECT_ZEROSCAN_OUT` can go (exp 0412).

## The count

| | Names |
|---|---|
| the inventory | 266 |
| read by today's shared build B | 266 |
| read by F (77 options gone, 4 more by exp 0418's table; 12 new: K1r 4, writers 1, save 4, title table 1, start-state skip 1, ioctl trace 1) | 197 |
| G takes out for certain: 11 deletes + `HEAP_GUARDS` + 23 library words + 3 ring words + 5 discarded hang-hunt words | -43 |
| **G, certain** | **154** |
| if he confirms the other five hang-hunt words and `FL_SERIAL`... (FL_SERIAL is one of the five above: `ARGS_WB`, `FL_SERIAL`, `FL_VGT_FLUSH`, `ARGS_FLUSH`, `ARGS_FLUSH_DRAWS`) | -5 |
| if `FORGET`'s arm says delete, the two timing words become constants, `LEARN_LOG` and `ZEROSCAN_OUT` go | -5 |
| **G at the least** | **144** |

Of G's 154: about 70 diagnostics and catchers (off), 39 one title's words in its table or its launcher data (42 less
exp 0418's three), 13 configuration, 3 general defaults with an option (`BC5_DIRECT_CHAIN`, `BC5_GC_MODE`, `BC5_GUARD_K1R`
with its filter counted as one rule), and the rest the lists above. **Without a verdict after G: 11**
(`LAZY_RELEASE`, `SPLIT`, `FORGET`, `CHAIN_HOLD_US`, `DCB_WAIT_MS`, `MAX_BO_MIB`, `AMM_SCATTER`, `AMM_SETBUFFER_MAP`,
`ANON_SYNC`, `SUBMIT_EOP_EVENT`, `PAD_TOUCH`); 10 once `FORGET`'s arm is read; each has an owner and a next step.
The class counts are sums of the lists in this directory and have not been re-derived from the built binary:
the first build of G must print its own list (`strings` of the binary against the inventory) before this table is quoted.
