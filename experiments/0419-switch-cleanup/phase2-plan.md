# Experiment 0419, phase 2 of the dead code: order of cuts and scripts (prepared 2026-11-14 on the laptop, no box)

One task after the night series, the test build T (patch fec3d656; normal b0abc471, lean b19b3e74) as the reference.
Aim: as few compile rounds as possible, at best one round and one acceptance.

## The six verdicts of 2026-11-14 (the top session, on this experiment's proposals)

| Word | Verdict | Where it lands |
|---|---|---|
| `BC5_DIRECT_MAX_BO_MIB` | delete | batch 1, step `bo` |
| `BC5_R3_SUBMIT_EOP_EVENT` | delete | batch 1, step `eop` (the read; its code goes with the R3 block in batch 3) |
| `KYTY_BC5_AMM_SCATTER` | diagnostic, off | stays as it is |
| `KYTY_BC5_AMM_SETBUFFER_MAP` | diagnostic, off | stays as it is |
| `KYTY_BC5_ANON_SYNC` | `verify` stays as a diagnostic; the `thread` form is cut | batch 3 |
| `KYTY_BC5_PAD_TOUCH` | the maintainer is asked | open: the only word without a verdict |

With these, words without a verdict: **1** (`KYTY_BC5_PAD_TOUCH`). After batch 1 the count of words that can be set
goes from 157 to 155.

## How one round is made to suffice

Every step is its own generator call on its own lines; a step whose compile fails is left out and the rest is
rebuilt, so one failing cut does not cost the others. Order on the box: (1) apply batch 1 and whatever of batches
2 and 3 is written by then to a copy of T's tree; (2) one build; on an error drop the failing step (the compiler
names file and line) and build again; (3) `strings` word list against the source list; (4) ONE acceptance
(`chk0419t.sh`) on the result. Nothing shared is touched. If the round cannot be closed in the slot, T stays as it is.

## Batch 1: written, dry-run on T's tree (`mkp2_0419.py`, five independent steps)

| Step | What goes | Lines | Checked on the laptop |
|---|---|---|---|
| `bo` | `BC5_DIRECT_MAX_BO_MIB`: its four lines in `kDMaxBo` | unit, -5 | edit matched once |
| `eop` | the read of `BC5_R3_SUBMIT_EOP_EVENT`; `submit_eop` stays false | unit, 1 line | edit matched once |
| `delay` | `KYTY_BC5_LOAD_DELAY`: `delay_ns_of` goes, `load_stat::delay` is an empty inline (five call sites stay) | `load_stat.hpp`, -31 | `-fsyntax-only -Wall -Wextra -Werror` clean |
| `flip` | `KYTY_BC5_MIN_FLIP_RATE`: `Bc5MinFlipRate` goes; the interval is `max(flip_rate, 0) + 1` | `videoOut.cpp`, -14 | edits matched once (file not compilable here) |
| `mem` | `KYTY_BC5_MEMORY_FROM_PARAM`: three constants, three functions, the saved total; the init line keeps its text with "off" | `memory.cpp`, -44 | edits matched once, every removed name gone (file not compilable here) |

All five together on T's tree: 5 insertions, 95 deletions in four files; braces balance; no new unused name in the unit.

## Batch 2: option-only cuts whose code is local (to write next; each about as small as batch 1's)

Named by their marker text `/* exp 0419: option removed */` in T's unit:

| Marker | Feature | Cut |
|---|---|---|
| `static const int mode = 0;` | a mode switch read once | fold the constant, drop the branches on it |
| `static const bool on = false;` and the `const char* e = nullptr;` after it (lazy-release block) | two readers next to `Lzr0401` | fold |
| `static const char* p = nullptr;` (F767's reader) | a path word | fold, drop its use |
| `static const int vma_fast = 0;` | the VMA fast path | drop the `if (vma_fast)` branches |
| `false /* ... */};` (an initializer's last field) | one flag of a struct | drop the field if nothing else sets it |
| `smp_parse(nullptr, &bad)` | the meshlet sampler's period | sampler off: its block goes with batch 3 |

## Batch 3: features woven through the unit (each a session of reading before any cut)

In rising order of size, with what must be read first:

1. `BC5_GUARD_FORGET` (the guardian's block and its test `test0412.cpp`: with the guardian).
2. The R3 block's dead members: `rewind`, `drop`, `submit_eop` and their code at the ioctl sites.
3. `KYTY_BC5_ANON_SYNC`'s `thread` form (`bc5/anon_sync.hpp` and its mode reader).
4. The acb CS prefix and acb inherit (`acb_inherit_mode`, the two `cap_parse(nullptr, ...)` rows, the journal lines).
5. The five hang-hunt words: in the unit `FlxSwitches::serial/flush`, `FlDraw::flush/serial`, `flx_heads`, the F1/F2
   inserts of `fl_after` and their part of the seams with `flx0401.cpp`; in the backend the write-back and the two
   flushes, and with them the four of step f in `indirect_check` and its Catch2 tests.
6. The guardian's mlock, cap, `MAP_RULE` and `PRT_BG` code (its list in `candidate-G.md`), with `test0412.cpp`.
7. The AMM PRT and extra commands in `libAmpr.cpp`.
8. The constant `if (Bc5...On())` branches of the 18 library units (several hundred sites, mechanical: one generator).
9. ADR 0013's consumer side (`hold_release`, the `hold` vectors).

Batch 3 cannot be promised for one round: items 4 to 6 each change the unit by hundreds of lines. The proposal for
tomorrow is batches 1 and 2 in the one round; batch 3 item by item afterwards, each with its own compile.
