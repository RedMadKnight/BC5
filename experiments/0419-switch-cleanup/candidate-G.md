# Experiment 0419: candidate G (patch 99f32d3b), made on the laptop on 2026-11-14, NOT built

Ordered by the top session for the night of 2026-11-13/14 with no box access. G's base is candidate F (d9af28ca).
F is not cleared for the swap (README sections 13 to 15: two rare, unexplained faults), so G is prepared, not proposed.

## What G is

| Piece | Value |
|---|---|
| patch 0001 (against KytyPlus f266548) | `99f32d3b` (`0001-new20.patch`), 132 patched files as F; 28 files differ from F, +100 / -699 lines |
| main unit `src/libs/bc5LleAgc.cpp` | `dd30a593` (F: 59d17cf5) |
| `src/bc5/switch_defaults.hpp` | `acd74fe6` (39 rows for the second title; F: 42) |
| backend `src/direct.cpp` | `9eb378e1` (F: exp 0412's 28100ce5); `direct.hpp` e96e5c73 as F: a new private archive is needed |
| tree list | `tree-candidate-G-99f32d3b.md5` |
| kit | shared notes folder, `exp0419-candidate-G/` (both patches, both tree lists, the two backend files, `p0419g.sh`, `F-to-G.diff`) |

Made by, in this order on F's tree: `mklibs0419g.py`, `mkg0419_a.py` to `mkg0419_e.py` (editor `ed0419g.py`: every
edit must match exactly once), and `mkg0419_f.py` on the backend file. `mkkit0419g.py` makes `p0419g.sh` from `p0419f.sh`.

## Word by word

| Words | n | What G does | Step |
|---|---|---|---|
| the 20 batch-2 `KYTY_BC5_LOAD_*` (NPTUS, NPPARTY, NPPARTNER, NPSNSFACEBOOK, VOICE, SCREENSHOT, DISCMAP, ULOBJMGR, COMPANIONHTTPD, COMPANIONUTIL, INVITATIONDIALOG, WEBBROWSERDIALOG, SHAREPLAY, GAMELIVESTREAMING, CAMERA, USBD, HMD, VRTRACKER, MOVE, NPAUTH), `KYTY_BC5_VOICE_PORTS`, `KYTY_BC5_NPTUS_FRIENDS_RUN` | 22 | **built in**: the tables are registered always, each unit's switch function returns true and reads nothing; nothing of a library runs before a title calls it; libUsbd no longer parses the allow list at registration. `KYTY_BC5_USBD_ALLOW` stays (a device list, default empty). The `if (Bc5...On())` branches inside the units are constant now and still in the source (several hundred sites) | libs |
| `KYTY_BC5_SEMA_TARGETED_WAKE`, `KYTY_BC5_EVENT_COALESCE_SAME` | 2 | **deleted with the code** | a |
| `KYTY_BC5_MUTEX_SPIN_US`, `_RING_SPIN_US`, `_TIMERSLACK_NS` (options gone in F) | (3) | **the code deleted**; `KYTY_BC5_RING_POLL_US` is the constant `kRingPollUs = 200` | b |
| `BC5_DIRECT_CROSS_RING_WAITS`, `_RING_DEPS`, `_TWO_RING_WAIT_MS` | 3 | **deleted with the code**: the two-ring wait block, `hold_keep_wait`, the holder thread and its statistics (ADR 0013's producer side: nothing could hold a chain on one ring); three title rows out | c |
| `BC5_DIRECT_TF_DEFAULT` | 1 | **deleted with the code**; with it `BC5_DIRECT_HS_OFFCHIP` (1 more word: read only inside TF_DEFAULT's block). Checked against exp 0418's table: `VGT_HS_OFFCHIP_PARAM` is still written from the title's own value | d |
| `BC5_DIRECT_PIECES_NO_CLEAR` | 1 | **deleted with the code** | d |
| `BC5_DIRECT_HEAP_GUARDS` | 1 | **constant on**, no option | d |
| `BC5_GUARD_MLOCK`, `_PIN_CAP`, `_CAP_ACT`, `_CAP_NAMES`, `_MAP_RULE`, `_PRT_BG` | 6 | **option gone, code still there (dead)**: the guardian's parser gets no value; `rule()` = 0, `prt_bg()` = false | e |
| `KYTY_BC5_AMM_PRT_CMDS`, `_AMM_EXTRA_CMDS` | 2 | **option gone, code still there (dead)** | e |
| `BC5_DIRECT_GPU_CHECK_ZERO`, `_GPU_CHECK_YZ`, `_FORCE_START_000`, `_ARGS_COPY` (backend) | 4 | **option gone, code still there (dead)** in `indirect_check` and its Catch2 tests | f |

43 words leave (42 of the plan and `BC5_DIRECT_HS_OFFCHIP`).

**Not deleted, against the order's wording ("dziewięć słów polowania ... usunięte z kodem"):** `BC5_DIRECT_ARGS_WB`,
`_ARGS_FLUSH`, `_ARGS_FLUSH_DRAWS`, `_FL_SERIAL`, `_FL_VGT_FLUSH`. The maintainer's "usunąć z kodu" was given on a plan
that called their hang classes gone; HANDOFF has F403 and F813 OPEN, none of the five ever had its deciding run, and
candidate F hung the GPU on 2026-11-13 in the way those classes describe (`undecided-plan.md`, the correction;
`candidate-G-plan.md`). `mkg0419_f.py <direct.cpp> all` removes the three backend reads (direct.cpp `aeec4c09`); the two
in the unit are one more small step. They go the moment he confirms the delete knowing this.

**Flag on one approved delete:** `KYTY_BC5_SEMA_TARGETED_WAKE` was approved under "measured as doing nothing", but its
only measurement is of load times (exp 0415), and it was written for F451 (the workers' wake-up), which HANDOFF has
OPEN with "no speed number for it exists". G deletes it as approved; if F451 is worked on again the code is step a's
reverse. F451's status line in HANDOFF must change with the swap.

## Checked, and not

| Check | Result |
|---|---|
| every generator edit matched exactly once; braces balance in every edited file; `#if/#endif` removed in pairs | yes |
| `-fsyntax-only -std=c++20 -Wall -Wextra -Werror` (VS clang++ 22, the tree's Windows configuration, the stand-ins of exp 0401's lib0405 check) on the 18 library units, `agc.cpp`, `semaphore.cpp`, `load_stat.hpp` | clean, or the same errors as F's file (`libNp.cpp`: `sched_param`; `agc.cpp`, `semaphore.cpp`: an unused parameter of today's code) |
| names defined and no longer used after the cuts (`unused0419g.py`, a stand-in for `-Wunused` on the unit) | 5 found and removed with their step (`hold_chain_held`, `hold_thread`, `hold_stats`, two counters); none left that F does not have |
| `test0419g.cpp` (the defaults header: 39 title rows, 37 taken when two are in the environment) | all ok |
| dry run of the box step: on a clean clone at F, `git apply -R 0001-new18` then `git apply 0001-new20`, all 132 files against `tree20.md5` | 0 differ |
| `p0419g.sh`: `bash -n` | ok; its stand-in run was NOT made (the build itself cannot run here) |
| `grep -c 'exp 0372'` in the patch; `pad_audio_route.hpp` present | 5; yes |
| **NOT checked: any compile of `bc5LleAgc.cpp`, `libAmpr.cpp`, `pthread.cpp`, `sync.cpp`, `main.cpp`, the backend with amdgpu; the link; any run** | the laptop has no Linux compiler: `p0419g.sh` on the box is G's first compile, and a compile error there is an expected kind of result |

## The dead code still in the source (phase 2, to be cut with a compiler at hand)

1. From G's own option-only steps: the guardian's mlock and cap code (`g412::Cfg::mlock/cap/cap_act/cap_names`,
   `cap_plan`, `guard0412_cap`, `guard0412_cap_changed`, the locker); for `MAP_RULE`/`PRT_BG` exp 0412 named what goes
   (`mr412::rule()`, `rule_for()` and its use in `direct_sync`, `prt_bg()`, `in_bg()`, `kBgLo`/`kBgHi`, `g_mr412_bg`, the
   background branch of `mr412_prt_open`, the `g_mr412_bg && mr412::in_bg` return) and what stays (`mr412_prt_open`,
   `mr412::classify`, `mr412_would_learn`). That code is inside the block its laptop test compiles
   (`G412_PURE_BEGIN..END`, `test0412.cpp`): the cut belongs with that test. The AMM PRT and extra commands in
   `libAmpr.cpp`; the four checks in the backend's `indirect_check` with their Catch2 tests.
2. From the library step: the constant `if (Bc5...On())` branches and the stub paths behind them in 18 units.
3. From E/F: 20 places marked `/* exp 0419: option removed */` (17 in `bc5LleAgc.cpp`, one each in `load_stat.hpp`,
   `videoOut.cpp`, `kernel/memory.cpp`). Behind them: the acb CS prefix and acb inherit paths, the sampler parse, the
   VMA fast path, `KYTY_BC5_LOAD_DELAY`, and smaller ones. Of F's removed options only the three spin/timer words lost
   their code in G.
4. ADR 0013's consumer side (`hold_release`, the `hold` vectors): still called, finds nothing, since step c.

Each of these is a mechanical cut, but the unit is 15560 lines that only the box compiles; doing them blind would
trade a night for compile rounds on the box. Proposal: phase 2 as one box session with the build at hand (CPU only,
no emulator), or after G's first build shows the method holds.

## Counts (from the source, `words0419g.py` and `settable0419g.py`; lists `words-candidate-F.txt`, `words-candidate-G.txt`)

| | read by the code | of them forced or unset at start (no option) | **can be set** |
|---|---|---|---|
| shared build B | 264 | - | 264 |
| candidate F | 247 | 47 | **200** |
| candidate G | 204 | 47 | **157** (39 one title's rows, 3 general defaults with an option, 115 other) |
| G if the five kept hang-hunt words go | 199 | 47 | 152 |

The earlier figures (197 for F, 155 for G) were sums of lists; these are counted from the trees and replace them.
The binary can hold fewer (the lean build compiles diagnostics out): G's first build must repeat it with `strings`.

Without a verdict after G: 16. The eleven of `candidate-G-plan.md` (`LAZY_RELEASE`, `SPLIT`, `FORGET`, `CHAIN_HOLD_US`,
`DCB_WAIT_MS`, `MAX_BO_MIB`, `AMM_SCATTER`, `AMM_SETBUFFER_MAP`, `ANON_SYNC`, `SUBMIT_EOP_EVENT`, `PAD_TOUCH`) and the
five hang-hunt words above. 11 once he confirms the five; 10 once `FORGET`'s arm is read.

## The open question: does F still change a line of `audio.cpp`?

Yes. F and G change three lines of `src/libs/audio.cpp` against B: one `#include "bc5/env_rule.hpp"` and the two read
sites of `KYTY_BC5_NO_PAD_AUDIO`, which now follow the one reading rule (`=0` is off). The pad route itself
(`pad_audio_route.hpp`, the `exp 0372` blocks) is byte-identical to B's. By the rule of 2026-11-13 the swap of F or
G therefore gets ONE software replug check. G also changes `libAudio.cpp` (the voice-port id map is always on); that
file is the Voice library's ports, not the pad's audio.

## What the proof on the box must cover (nothing of it is done)

Both titles, start and walk, with the libraries built in (ASTRO BOT x3: a title that imports one of the 20 libraries
now gets the ported answers instead of a stub; neither title's import list was read for this); the cutscene arm; the
lean build; the list of words from the binaries.
