# Experiment 0419: build W = V + the lean build without its diagnostic switches, prepared 2026-11-15 on the laptop; built and accepted the same morning

The maintainer, through the top session: a reminder that the lean version is to
have every diagnostic switch cut from its code and, on the one exception, the record of a GPU fault may stay. In build U the lean binary still
held 191 of the 203 words the source reads. The normal build is not changed by W.

## How

`mklean0419.py <tree> lean-classes.tsv <the backend's direct.cpp>` rewrites how a word is read; the macros are in
`src/bc5/env_rule.hpp`:

| Class | Words | In the lean build | In the normal build |
|---|---|---|---|
| D: diagnostics, catchers, test hooks (`lean-classes.tsv`) | 90 | `BC5_DIAG_ENV("W")` is a null pointer; a helper call becomes `BC5_LEAN_OR(off, helper("W"))` = off. The name is not in the binary and the code behind the constant "off" is dropped by the compiler | the call that stood there |
| U: unset at start (`kIgnored`) | 14 | the same | the same |
| F: forced at start (`kFixes`, `kDefaults`) | 35 | `BC5_FIXED_ENV("W", "<value>")` is the row's value as a literal (or `BC5_LEAN_OR(true, ...)`); the name is not in the binary | the call that stood there (the row still forces it) |
| K: kept | 69 | read as today | read as today |

A row of `kFixes`, `kDefaults` or `kIgnored` whose word lean no longer reads by name is left out of the lean build's
table (39 of 49 rows), and the lean build's old list of words to unset in `main.cpp` (exp 0177) goes: nothing reads
them.

On V's tree: 80 words rewritten at 88 sites in 26 files; with the 37 words that exp 0177 had already put behind
`BC5_DIAG_ENV`, 117 words leave the lean binary.

## What lean reads after W: 69 words

38 rows of one title, the 3 defaults with an option, and 28 kept (`lean-keep.txt` is the list `strings` is checked
against):

- **14 configuration words**: `BC5_DIRECT_EAGER_NAMES`, `BC5_DIRECT_LAZY_NAMES`, `KYTY_BC5_USBD_ALLOW`,
  `KYTY_BC5_HAPTIC_GAIN`, `KYTY_BC5_INPUT_CONFIG`, `KYTY_BC5_KEY_MIN_HOLD_MS`, `KYTY_BC5_LOGIN_USERS`,
  `KYTY_BC5_MANGOHUD`, `KYTY_BC5_MENU_DIR`, `KYTY_BC5_PAD_AUDIO_DEVICE`, `KYTY_BC5_RT`, `KYTY_BC5_RT_BUILD_PGM`,
  `KYTY_BC5_SAVEDATA_DIR`, `KYTY_BC5_TRIGGER_DEADZONE`;
- **3 user settings**: `KYTY_BC5_NO_PAD_AUDIO`, `KYTY_BC5_PAUSE_ON_BACKGROUND`, `KYTY_BC5_PAD_SPEAKER`;
- **10 words of opt-in behaviour, kept and each waiting for a ruling** (they are neither configuration nor a
  default with an option, so they do not fit "configuration + title rows + 3"): `BC5_DIRECT_FLIP_DEFER`,
  `KYTY_BC5_JOB_ARENA_FIX`, `KYTY_BC5_MAP_RECORDS`, `KYTY_BC5_MAP_RECORDS_CHECK_MS`, `BC5_GUARD_K1R`,
  `BC5_GUARD_K1_FILTER`, `BC5_GUARD_LAZY_BY_DATA` (the guardian's, under its verdict), `KYTY_BC5_SAVEDATA_MEMORY_PARAM`,
  `KYTY_BC5_SAVEDATA_MEMORY_SLOTS`, `KYTY_BC5_SAVEDATA_TRANSFER_FIX`. With all ten ruled (a constant or gone) lean
  reads 59;
- **1 test hook kept on purpose**: `KYTY_BC5_INPUT_CMD`. The scripted route is driven through it; without it the
  lean build cannot be walked, so it could not be measured. The top session's to rule.

## Named and still in the lean binary after W: 16 words (none can be set to any effect, except as noted)

| Words | Why they stay | Effect in lean |
|---|---|---|
| 8 forced `BC5_R3_*` (`MPROTECT_GAPS`, `NULL_ARGS`, `RELEASE_HOLES`, `MUNMAP_HOLES`, `FLEX_HINT`, `DMQ_END`, `EXEC_EINVAL`, `QUERY_SIZE`) | read through a table of names in `memory.cpp` | forced on by their rows, as today |
| `KYTY_BC5_FW_AUDIO` (forced) | read by a helper that returns a set of items | forced on by its row, as today |
| `BC5_DIRECT_IB_MAX_DW` (unset at start) | read by the BACKEND, whose archive is one for both builds | unset at start by its row, as today |
| `BC5_DIRECT_DRAW_ARGS_JOURNAL` (diagnostic) | read by the BACKEND | unset at the lean build's start (a lean-only line in `switch_defaults.hpp`) |
| 4 reset switches (`BC5_DIRECT_RESET_REPLAY_ACB`, `_RESET_LABELS`, `_LEARN_GUEST_ONLY`, `_RESET_LABEL_JOURNAL`) | their names stand in a table used for one journal line; they are constant off since E | none: dead code of batch 3 |
| `KYTY_BC5_ANON_SYNC_MS` | read through a numeric helper | none: its thread only starts with `KYTY_BC5_ANON_SYNC`, which lean no longer reads |

They go with: a lean backend archive (2 words), the reset switches' cut (4), and three small helper changes (10).

## The GPU fault record in lean (the maintainer: kept)

`BC5_FAULT_RECORD` is not an option since candidate E (unset at start; the record is always on) and its reader treats
"no word" as on, so the lean build keeps the behaviour with no extra step: a GPU fault or a GPU hang ends the game
with exit 86 and a record under `~/bc5-data/captures/faults/`.

What of the diagnostics stays in lean as part of the record (read in `fr412_record_and_exit`):

- `record.txt`: time, the fault address and status, READ or WRITE or "a hang without a page fault", the address's
  kind (`mr412::classify`), its view, heap and chunk, pinned memory, and the save guard's outcome;
- `layout-views.txt`, `layout-buffers.txt`, `layout-mappings.txt`;
- `meminfo.txt`, `pressure.txt`, `environment.txt` (every `BC5_*` and `KYTY_*` variable), `process.txt`;
- the save guard before the exit (a save in flight is let finish, the save directory synced) and exit 86.

What a lean record does NOT have, because it comes from catchers that leave lean with their code:
`journal-tail.txt` (lean keeps no journal), `pointers.txt` (ph412), the timeout layout (tl412), the dispatch counts
(dc412), the snapshot on a timeout, the timeout probe's summary. `dmesg.txt` and `build.txt` are added by the
launcher and do not depend on the build.

## Checked on the laptop

- the generator on V's tree: 80 words, 88 sites, 26 files; every file keeps its line endings; the include of
  `bc5/env_rule.hpp` is added where it was missing;
- `-fsyntax-only -std=c++20 -Wall -Wextra -Werror` in BOTH modes (with and without `-DBC5_LEAN=1`) on the 24 changed
  `.cpp` files, against V: the 12 that the laptop can compile (`hostException`, `eventQueue`, `fileSystem`,
  `semaphore`, `libAudio2`, `libKernel`, `libNpCppWebApi`, `libRtc`, `libRudp`, `libSaveData`, `libSystemService`,
  `network`) are clean in both modes; the other 12 stop at a missing system header as they do for V;
- `test0419diag.cpp` against W's `switch_defaults.hpp` in the normal mode: all ok. In the lean mode six of its checks
  fail by design (they assert the forced rows, which the lean build no longer applies): the test is the normal
  build's.

## NOT checked

- Any compile of the main unit, `main.cpp`, `memory.cpp`, `audio.cpp`, `libAmpr.cpp`, `ajm.cpp` and the other files
  the laptop cannot build, in either mode. In lean mode a helper lambda (`take`) and a few locals lose their last use:
  warnings are expected, the host build does not make them errors.
- That the compiler really drops the code behind a constant "off" (it is asked to, not forced to): the lean binary's
  size and `strings` list are the check, on the box.
- Whether the normal binary is byte-identical to V's (the macros expand to the same calls, but 26 files gain an
  include line, which moves line numbers).
- Speed: whether lean got slower or faster. The round measures it (below).

## The round (one compile; the box, a slot of its own)

`p4build0419.sh` (kit: it, `mklean0419.py`, `ed0419g.py`, `lean-classes.tsv`, `lean-keep.txt`, `words-build-V.txt`,
V's tree list as `treeV.md5`, `tree-build-W.md5` as `treeW.md5`): checks the tree is V's, saves `src/` and both
binaries, rewrites, rebuilds normal and lean, then lists the lean binary's words against `lean-keep.txt` (what is in
it and not meant to be, what is meant to be and is not). Then the acceptance of both builds as for V, and for the
speed question three lean walks of the second title on W's lean binary against three on V's lean binary, interleaved
(flips a second, the longest gap; the lean build writes no journal, so the launcher's own lines are the measure).

## Built and accepted (2026-11-15 07:58 to 08:40, the box)

**The variant built** (no ruling had come by then; the top session's order said to finish W unchanged): the nine
opt-in words out of lean as proposed (`lean-classes-ten.tsv`, `lean-keep-ten.txt`); `BC5_DIRECT_FLIP_DEFER` stays in
lean, because `~/bc5-work/bc5-run.env` sets it (`=1`) for the menu and the first title. The four reset names and
`KYTY_BC5_ANON_SYNC_MS` are cut from lean too. Raw: `raw/chk0419x.out` (acceptance, build, speed).

**Build** (`VARIANT=ten v0419round.sh buildw`, 07:58:53 to 08:00:47): **compiled at the first attempt**; the box's
tree is the laptop's (0 of 133 files differ). Normal `04e986fb` (54 warnings in the rebuilt files), lean `5670ab77`
(58). Copies: `~/bc5-work/exp0419/bin-W/`.

**Words in the binaries** (`strings`, against the 202 words V's source reads):

| | V | W |
|---|---|---|
| normal build | 196 | **196** (unchanged) |
| lean build | 190 | **72** = the 60 words lean is meant to read (`lean-keep-ten.txt`: 38 title rows, 3 defaults with an option, 14 configuration words, `FLIP_DEFER`, 3 user settings, `KYTY_BC5_INPUT_CMD`) + 12 named leftovers |

Every word lean is meant to read is in the lean binary; nothing else is, except the 12 named: the 8 forced
`BC5_R3_*` and `KYTY_BC5_FW_AUDIO` (forced on by their rows, read through a table or a helper), the two words the
backend reads (one archive for both builds; `BC5_DIRECT_DRAW_ARGS_JOURNAL` is unset at the lean build's start,
`BC5_DIRECT_IB_MAX_DW` is unset by its row), and `KYTY_BC5_MAP_RECORDS_CHECK_MS` (its helper; `MAP_RECORDS` itself
is not read in lean, so it has no effect).

**Acceptance** (`chk0419x.sh`, 08:01 to 08:26, every switch unset, RT on, no pad key):

| Run | Result |
|---|---|
| x0a, x0b, x0c: the first title 120 s, fresh save directory | PASS three times, 0 kernel lines, 0 crash lines |
| x0f: the first title 30 s on the kept bad save | PASS |
| x1a: the second title's walk to G+240 | clean: 25.5 flips/s over 355 s, longest gap 833 ms, 0 kernel lines |
| x2cuta: the cutscene arm to G+320 | clean: 29.9 flips/s; longest gap 1,860 ms (V: 407 ms). The frame profile puts a 1,228 ms frame at 44.7 s, during the load (gameplay began at 111 s), with the game thread 1,203 ms inside the host; one run, not followed |
| x3l: the second title on the lean build, 120 s | PASS |
| **x4l: the first title on the lean build, 120 s (new)** | PASS |

**Did lean get slower?** Six lean starts of the second title, interleaved V W V W V W, 120 s each, measured between
60 s and 115 s of each run (`leanspeed0419.sh`; the lean build has no flip counter, so the measure is the process's
CPU time and its GPU time on the gfx and compute engines, both per second of wall time; the two engines are summed,
so the GPU figure can exceed 1,000 ms/s):

| Run | CPU s/s | GPU ms/s |
|---|---|---|
| V a / W a | 4.964 / 4.993 | 1,362.0 / 1,368.3 |
| V b / W b | 4.926 / 4.923 | 1,322.1 / 1,336.3 |
| V c / W c | 4.963 / 4.829 | 1,338.4 / 1,145.7 |
| mean V / W | **4.951 / 4.915** | **1,340.8 / 1,283.4** |

No clear rise in measured CPU/GPU use; lean fps/frametime not measured (CPU s/s and GPU ms/s are use, not render
speed: LESSONS R13, Codex 2026-11-15 10:07). W's figures are V's within the run-to-run spread (W c's lower GPU time is one run; without it W's mean
is 1,352). The start screen with no input is all this measures; a walk on the lean build is not measured (the route
needs the flip lines lean does not print).

**Not done:** the software replug of W. W changes no pad or audio code (its edits are reads of words; the pad files
are V's, whose replug R12 passed), so by the rule of 2026-11-13 none is owed.
