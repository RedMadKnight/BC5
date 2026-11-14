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

All seven steps (with batch 2's two) together on T's tree: four files, about 120 lines less; braces balance; no new unused name in the unit.

## Batch 2: two more steps of the same script, read and dry-run on T's tree

| Step | What goes | Lines |
|---|---|---|
| `names` | `KYTY_BC5_NAMES_FAST` (option gone since E, mode was the constant 0): the memo path of `ls415_name_class`; the name's class is asked as when unset | unit, -10 |
| `vma` | `KYTY_BC5_VMA_FAST` (option gone since E, the constant 0): the binary-search path of `inside_vma`; the walk stays | unit, -12 |

Read and NOT local, so moved to batch 3: the zero skip's two readers (`lzr_zero_skip`, `zskip_path`: the whole
exp 0379 zero-skip block hangs on them), the four reset switches of `m11_on`, and the meshlet sampler's period.

## Batch 3: features woven through the unit (each a session of reading before any cut)

In rising order of size, with what must be read first:

0. The zero skip of exp 0379 (`lzr_zero_skip`, `zskip_path` and what hangs on them), the four reset switches
   (`m11_on`), the meshlet sampler.
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
tomorrow is batches 1 and 2 (seven steps, one script) in the one round; batch 3 item by item afterwards, each with its own compile.

## Done: the one round (2026-11-14 15:32 to 15:57, the box; the maintainer's "zrób w pierwszej kolejności")

Build **U** = the test build T + ten steps of `mkp2_0419.py` (the seven above and three from the verdicts): patch
`5b185960` (133 patched files, `tree-build-U-5b185960.md5`), normal `b85a756d`, lean `e8c3d935`. Raw:
`raw/chk0419u.out`. The files and binaries of T are kept on the box in `~/bc5-work/exp0413/p/p2-before/`.

| Step | Compiled at the first attempt | What was cut |
|---|---|---|
| `bo` | yes | `BC5_DIRECT_MAX_BO_MIB` with its lines |
| `eop` | yes | the read of `BC5_R3_SUBMIT_EOP_EVENT` |
| `names` | yes | the memo path of `KYTY_BC5_NAMES_FAST` |
| `vma` | yes | the binary-search path of `KYTY_BC5_VMA_FAST` |
| `forget` | yes | `BC5_GUARD_FORGET`: the call, the declaration and `guard0412_forget` |
| `anonthread` | yes | `KYTY_BC5_ANON_SYNC`'s `thread` form: any set value is `verify` now; the skip of the walk is gone |
| `delay` | yes | `KYTY_BC5_LOAD_DELAY` |
| `flip` | yes | `KYTY_BC5_MIN_FLIP_RATE` |
| `mem` | yes | `KYTY_BC5_MEMORY_FROM_PARAM` |
| `touch` | yes | `KYTY_BC5_PAD_TOUCH` (the maintainer: "usuń"): the forwarding of touch points in `window.cpp`; the touchpad click (F252, a button) is untouched |

**No step was taken back.** One build of normal and lean (`p2build0419.sh`, 15:32:28 to 15:33:56, 37 warnings in the
rebuilt files); the backend is not changed by this round (its 121 tests ran for T). CPU tests on the laptop:
`test0419diag.cpp`, `test0419g.cpp`, `ajm/test0419ajm.cpp` unchanged and passing; exp 0412's tests were not run again
(the round removes `guard0412_forget`, which is outside the blocks they compile).

**Acceptance of U** (`chk0419u.sh`, every switch unset, RT on, no pad key, one lock line):

| Run | Result |
|---|---|
| u0a, u0b, u0c: ASTRO BOT 120 s from a fresh save directory | PASS three times, 0 kernel lines, 0 crash lines |
| u0f: ASTRO BOT 30 s on the kept bad save | PASS |
| u1a: the second title, menu, load, walk to G+240 | clean: 25.5 flips/s over 353 s, longest gap 771 ms, 0 kernel lines, 0 crash lines |
| u2cuta: the cutscene arm, 320 s without input | clean to G+320: 29.9 flips/s, longest gap 594 ms, 0 kernel lines |
| u3l: the lean build 120 s | PASS |

The second title's journal still says "lazy release ... on (30 s, eager)" and "chains ... up to 2000 us".

**Words, final for U** (from the source, `words-build-U.txt`): 203 read, **154 can be set** (36 rows of one title, 3
general defaults with an option, 115 other). The shared build B: 264, all settable. **Words without a verdict: 0.**

**Dead code still in the source after this round** (none of it is a cut that was taken back; each is named because
the aim was 0):

| What | Why it is still there |
|---|---|
| `ControllerTouch` and the touch fields of the pad state (`controller.cpp`), now unreachable | woven into the pad's state and its read-out; `controller.cpp` is pad code and was left alone |
| `g412::forget_step` (the pure function `guard0412_forget` called) | inside the block exp 0412's CPU test compiles: goes with that test |
| the R3 block's `submit_eop`, `rewind`, `drop` members and their code at the ioctl sites | batch 3, item 2 |
| the checking thread of `KYTY_BC5_ANON_SYNC` | it serves `verify`, which stays as a diagnostic |
| the zero skip of exp 0379 (`lzr_zero_skip`, `zskip_path` and what hangs on them), the four reset switches (`m11_on`), the meshlet sampler | batch 3, item 0 |
| the acb CS prefix and acb inherit | batch 3, item 4 |
| the five hang-hunt words' code (unit and backend) and step f's four checks in `indirect_check` | batch 3, item 5 |
| the guardian's mlock, cap, `MAP_RULE`, `PRT_BG` code | batch 3, item 6 |
| the AMM PRT and extra commands (`libAmpr.cpp`) | batch 3, item 7 |
| the constant `if (Bc5...On())` branches of the 18 library units | batch 3, item 8 |
| ADR 0013's consumer side | batch 3, item 9 |

**Binaries' word lists** (`strings`, against the source list): the normal build holds 197 of the 203, the lean build
191 (the absent ones are diagnostics compiled out by their gates, the same six and twelve as in T). `MAX_BO_MIB`,
`SUBMIT_EOP_EVENT` and `PAD_TOUCH` are in neither binary. Copies of both binaries with their md5s and word lists:
`~/bc5-work/exp0419/bin-U/` on the box.

**The software replug: NO TEST.** The round does not touch `audio.cpp`, `pad_audio_route.hpp` or `controller.cpp`,
but it changes the pad's touch events in `window.cpp`, so one software replug was run on U's private normal build
(`../0413-np-session-v2-shared/integration/replug/go0391.sh R11 pulls`, pins `pins0391-U-private.env`, raw `R11-*`
there). Its harness did not start the pulls: "no DualSense ALSA card in PipeWire" (15:58:30); after the run the box
showed no joystick device and no DualSense in PipeWire, so the pad was off or asleep (it was present during the
acceptance: one joystick watched). The run under it was clean (420 s, 0 kernel lines, 0 crash lines), but that is
not a replug check. **Owed:** one software replug of U with the DualSense on, before U goes anywhere shared. No
physical replug is asked for.
