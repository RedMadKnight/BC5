# 0417 — follow-ups to the shared builds of 2026-11-13 (patch 0001 4651d1d3)

**Question.** After the integration of exp 0416 + 0415 + 0412 (`../0416-emufive-switches/integration/README.md`), which
of its open points can be closed or prepared on the laptop, without the box, so that the next slot and the next swap
are short? The top session's list of 2026-11-13: the wording of one line, a line for the silent code defaults, a hook
that forces set-buffer's a4 = -1 on a real call, the two other launchers, CLAUDE.md, the replug harness's self-test,
the submit-owner note to exp 0415.

**Status: laptop work done; the candidate patch was built PRIVATELY with the test hook and the hook ran in six ASTRO
BOT starts on 2026-11-13 (section 2b). Nothing is in the shared builds.** The patch on main
stays 4651d1d3 (it must match the shared builds, D19).

## Setup

Branch `exp/0417-shared-followups` on main `7d21b208`. KytyPlus f266548 with patch 4651d1d3 as the pinned input.
Laptop: VS clang++ 22 for the CPU tests (`-std=c++20 -O1 -Wall -Wextra -D_CRT_SECURE_NO_WARNINGS`).

## Result

### 1. The next small patch change (`mk0417.py`; rides with the next swap, not its own)

Candidate patch 0001 **33bddfa1** (126 files; 4651d1d3 plus `0417-on-4651d1d3.diff`; it was c61fe48b before A2's
line was added; sums of all patched
files in `tree-candidate.md5`). The full candidate is not in the repository (the repository's line-ending rule would
change it outside `backend/kytyplus-patches/`); it is made by `mk0417.py` on the pinned units, and a copy lies in the
sessions' shared notes as `exp0417-0001-candidate-33bddfa1.patch`.

| Unit | In -> out | Change |
|---|---|---|
| `src/libs/libAmpr.cpp` | a2d09d32 -> 1cdf1424 | exp 0416's line no longer says "a target that is not mapped" when exp 0413's guard is off; it says the guard did not take the call. The test hook (below), compiled out. |
| `src/bc5/setbuffer_test.hpp` | new -> 56589d82 | `KYTY_BC5_SETBUFFER_TEST_HOOK 0`: the hook's compile-time gate |
| `src/libs/bc5LleAgc.cpp` | a81efd2c -> 30f9ef2b | A2's line "exp 0401: acb state restore (exp 0381) on/off" also goes to stderr, once (the top session: the lean build has no journal) |
| `src/kernel/memory.cpp` | eff24b4c -> 3844ef65 | `KYTY_BC5_RANGES_FAST` (C2) prints "exp 0412 ranges fast: on/off" once at its first use; `KYTY_BC5_PHYSMAP_SORTED` (C3) now also prints "off" |

**What a log shows for `KYTY_BC5_SWITCH_DEFAULTS=0` after this change** (the code defaults of `kFixes` must stay on):
C1 "exp 0412 events: pending cap 64" (play log, exists), C2 "exp 0412 ranges fast: on" (play log, new), C3 "exp 0412
physmap sorted: on" (play log, exists; "off" is new), the APR row "exp 0415: APR reads by pread ..." (play log,
exists), A2 "exp 0401: acb state restore (exp 0381) on" (the journal as before, and now the play log).
C2's and A2's lines are printed at the first use of their code, which ASTRO BOT's first 30 s do not reach (section 2b).

### 2. The hook: a forced a4 = -1 on a real call (`KYTY_BC5_AMM_SETBUFFER_TEST`, private builds only)

Why: in patch 4651d1d3 no title call had a4 = -1 in 21 ASTRO BOT starts, so the guard and the map opt-in ran only in
a CPU test with stand-ins. The hook is compiled only when `KYTY_BC5_SETBUFFER_TEST_HOOK` is 1; the header says 0, so a
shared binary cannot have it. A private kit sets the header's value to 1 (one file recompiles).

| Value | What it does | What must follow |
|---|---|---|
| `mapped[:N]` | the title's Nth set-buffer call (default the first) gets a4 = -1 (and a3 != va if needed): the map signature on the title's own committed buffer | guard on: exp 0413's line, the buffer attached, the title runs on. Guard `=0` and `KYTY_BC5_AMM_SETBUFFER_MAP=1`: the map flavour over the title's memory, exp 0413's crash (a negative control only) |
| `unmapped[:N]` | before the Nth call, one synthetic call with the map signature on an address nothing is mapped at (`KYTY_BC5_AMM_SETBUFFER_TEST_VA`, hex, default 0x8ff0000000; skipped with a line when something is there); the title's own call is not changed | map opt-in off: exp 0416's line, nothing mapped, the hook's line "after no". Opt-in on: the real `ExecuteAmmMapCommand` runs; the hook prints its return value and the kernel query's answer after it |

Every hook action prints a line that starts "[bc5] exp 0417 hook:".

**CPU tests** (`mktest0417sb.py`: the real functions cut from the edited unit, exp 0416's stand-ins):
- hook compiled out (as a shared build): exp 0416's four runs (guard on/off x opt-in off/on), PASS x4;
- hook compiled in, nine processes, PASS x9: unset (no line, three attaches); `mapped:2` with guard on (1 refusal
  line, 3 attaches, nothing mapped), with the opt-in too (the same), with guard off (exp 0416's line, nothing
  mapped), with guard off and the opt-in (the second call maps: the old bug, as intended); `unmapped` (exp 0416's
  line, nothing mapped), with the opt-in (one map of the test page, "after YES"), with guard off (as the first), and
  with the test va on a committed page ("is committed, nothing done").

Not shown by these tests: the real `KernelVirtualQuery` and `ExecuteAmmMapCommand` (stand-ins here); whether
0x8ff0000000 is free and mappable in ASTRO BOT's AMM state (the pool may not be given yet at the first call: then the
map fails and the hook prints the error code, which is a result); whether a 0x100-byte scratch header passes the real
`ValidateCommandBufferHeader`.

**The kit for that slot** (`mkkit0417.py` makes `p0417.sh` from the integration's private rebuild script;
`chk0417.sh` is the chain): the private tree goes from 4651d1d3 to c61fe48b, the gate is set to 1 in the private tree
only, the normal build is rebuilt (two units recompile), the gate goes back to 0, then six ASTRO BOT starts of 30 s:
mapped, mapped with the opt-in, unmapped, unmapped with the opt-in, `KYTY_BC5_SWITCH_DEFAULTS=0`, nothing set. A
start that does not run its 30 s is a result and the chain goes on; a kernel line stops it. Checked on the laptop:
`bash -n` of both scripts and a dry run of the gate switch (the header returns to its sum). About 12 minutes on the
box. Not in the kit: the mapped arm with the guard off and the opt-in on (exp 0413's crash, already proved). If the
build fails the gate stays at 1 in the private tree; the next private rebuild then stops at its tree check.

### 2b. The hook on the box (2026-11-13 07:05-07:12, the top session's slot; `chk0417.sh`, output in `raw/chk0417.out`)

Private build of the candidate 33bddfa1 with the gate at 1: **normal d85d86176e3eb1cbe7b9f703809fc104** (282
warnings in the build log; the hook compiled in the real unit at the first try). The gate was set back to 0 in the
private tree. Six ASTRO BOT starts of 30 s on that binary; all six PASS (ran 30 s, 0 kernel lines, 0 crash lines):

| Tag | Words | What the log shows |
|---|---|---|
| h1x0 | `KYTY_BC5_AMM_SETBUFFER_TEST=mapped` | the title's first call (va 0x300a82820, len 0x400, leftover a4 0x9088e4e98) got a4 = -1; the target is committed; **exp 0413's guard: "taken as the buffer flavour, nothing mapped"**; the title ran on |
| h2x0 | mapped and `KYTY_BC5_AMM_SETBUFFER_MAP=1` | the same: the guard refuses before the opt-in is asked (va 0x300a807a0) |
| h3x0 | `KYTY_BC5_AMM_SETBUFFER_TEST=unmapped` | the synthetic call on 0x8ff0000000: **exp 0416's line "taken as the buffer flavour"**, returned 0, "committed before no, after no (nothing mapped)" |
| h4x0 | unmapped and `KYTY_BC5_AMM_SETBUFFER_MAP=1` | the synthetic call returned 0, **"committed before no, after YES (mapped)"**: the real map command ran; no exp 0416 line |
| h5x0 | `KYTY_BC5_SWITCH_DEFAULTS=0` | "pending cap 64", "physmap sorted: on", the APR line: C1, C3 and the APR row stay on without the table |
| h6x0 | nothing set | no hook line; the same three lines |

So the check that chance stopped providing is made on real calls: with the map signature on the title's own mapped
buffer the guard refuses (with and without the opt-in), and on an unmapped address nothing is mapped unless
`KYTY_BC5_AMM_SETBUFFER_MAP=1`, in which case the real `ExecuteAmmMapCommand` maps it.

What these six starts do not show:
- **C2's and A2's lines appear in none of them**: "exp 0412 ranges fast" and "exp 0401: acb state restore" are printed
  at the first use of their code, and ASTRO BOT did not reach either in 30 s. They need a start of the second title
  (or a longer ASTRO BOT run) to be seen; for ASTRO BOT `KYTY_BC5_SWITCH_DEFAULTS=0` is checkable for C1, C3 and the
  APR row only.
- h3x0: the synthetic call's buffer flavour wrote its pointers into the hook's scratch header and returned 0, so the
  real header check accepts a zeroed 0x100-byte header; nothing else used that header.
- h4x0 leaves one 16 KiB page mapped at 0x8ff0000000 for the rest of the run (a test's side effect).
- The arm "mapped, guard off, opt-in on" was not run (exp 0413's crash, proved there).
- One start per arm; ASTRO BOT only; the hook is not in any shared binary and was not run in the second title.

**Side effect on the box:** `~/bc5-work/exp0413/p/build-normal` (d85d8617) now carries the test hook and is patch
33bddfa1's, so it is **no longer the twin of the shared normal build** (fe0933c0, patch 4651d1d3). The private lean
build (a569bb99) is still patch 4651d1d3's. The private tree is the candidate with the gate at 0.

### 3. `play-pkg-log.sh` and `play-pkg-quiet.sh`

Read on the box on 2026-11-13 05:18 (the top session's GO for reads only; no lock, nothing started):
`play-pkg-log.sh` 5080d2ce (147 lines) and `play-pkg-quiet.sh` 48fa60ba (141 lines), both last changed 2026-10-26.

**They are not `play-pkg.sh` minus exp 0413's change: they are copies from 2026-10-16.** Against `play-pkg.sh`
157021e3 the log copy lacks 94 lines and the quiet copy 96 (the lean switch, `BC5_EMU`, the TF ring, the
reflections' settings, the RT-on guards, the start delay, the unpacked title, `ulimit -c 0`, the title's 20 switch
words, ...). What each has of its own is small: the log copy writes the guest's printf to a file in the capture
directory; the quiet copy does that too and sets `BC5_LOGGING=0` with no timing, no frame profile and no per-second
counters. No desktop shortcut names either file; only old run scripts in `~/bc5-work` do (`route.sh`, `bisect.sh`,
`run57x.sh`, ...).

`mkpkg0413.py` does apply to both (its anchors exist), but the result would still be three weeks behind. So the
proposal is to make both again from the current launcher (`mklaunch0417.py`, input pinned to 157021e3):

| File | Made from `play-pkg.sh` with | Diff against `play-pkg.sh` | Against the file on the box | md5 |
|---|---|---|---|---|
| `play-pkg-log.sh` | printf to a file | `play-pkg-log-vs-play-pkg.diff`, 4 marked lines | 21 lines out, 96 in | 02274778 |
| `play-pkg-quiet.sh` | printf to a file, `BC5_LOGGING=0`, no timing, frame profile or counters | `play-pkg-quiet-vs-play-pkg.diff`, 8 marked lines | 17 lines out, 98 in | 330be87a |

Both parse (`bash -n`). **Not installed and not run.** With `BC5_LEAN=1` the capture directory does not exist, so the
printf file is then `~/bc5-work/play-pkg-guest-printf.txt`. The maintainer's choice: install these two, or retire the
two files (nothing he starts uses them).

### 4. CLAUDE.md

`CLAUDE-md-update.diff` (applies on main 03de9b8c with `git apply`), with the versions read on the box on 2026-11-13
05:18: kernel 7.2.15-ogc1.1.fc45 (`uname -r`), Mesa 26.2.6 (`rpm -q mesa-vulkan-drivers`: 26.2.6-2.fc45), libdrm
2.4.134 (`rpm -q libdrm`: 2.4.134-2.fc45; `ldd` shows the shared emulator loads the host's
`/usr/lib64/libdrm_amdgpu.so.1`); `mem_info_vram_total` 536,870,912 (512 MiB, as D8 says). The Mesa in the `ubuntu`
build container was not read (the emulator does not load it). The diff also gives the shared builds' paragraph for
patch 4651d1d3, its code defaults and the two exp 0412 switches that must stay unset; the launcher 157021e3 and the
state of the two copies; the Wayland socket `wayland-1`. Not applied here: the top session merges it.

### 5. The replug harness's self-test

`test0391.sh` (stand-ins, laptop only), run from a temporary sibling directory so that its path to exp 0372's files
resolves: **passed 29, failed 0**, with tonight's `run0391.sh` (the shared build again, `E0391_BUILD`) and pins. It
uses a stand-in for `s6n0391.sh`, so the launcher edits of that script are not covered by it; those were checked by
the dry run of the integration and by R7 and R8 on the box.

### 6. The submit-owner note

`../0416-emufive-switches/DESIGN-submit-owner.md` was sent to exp 0415's session (it owns the lock side, stages
S2-S5 of its `DESIGN-lock-side.md`) with three questions: fit or overlap, what is unsafe from its measurements, and
drop / fold / later. No code.

**Its answer** (`REVIEW-submit-owner-by-0415.md`): not dropped and not built apart; it is a later stage of the lock
side, after S2-S4 ("the applier of change records also owns the CS ioctl"). The note's premise is dated (the
maintenance is 540-860 full syncs per phase, not a few long holds), its point 1 is unsafe as written (the probe, the
filter and the state prefix read mapping and ring state), its point 4 would change the cross-ring order that
`BC5_DIRECT_RING_DEPS` protects, and the callers that matter still wait for their own entry. Three counters come
first, among them one table of the callers of `submit_now` and the holders of `g_dev_mutex` for both designs. The
note itself is not edited (it lies in exp 0416's directory); this review stands beside it.

The same message corrects a reading of the integration's runs: the route times that did not move with the APR
default are the runner's gate (its first key goes at 85 s or later), not a missing effect.

## 7. The next patch change: candidate c55174b1, built privately and checked (2026-11-13 09:04-09:54)

Ordered by the top session on the maintainer's word that the learned windows go. Patch 0001 4651d1d3 ->
**c55174b1** (127 files; sums in `tree-candidate-c55174b1.md5`; the full patch is in the sessions' shared notes as
`exp0417-0001-candidate-c55174b1.patch`). Not in the shared builds: one more fold is ordered first (exp 0412's K1r
rule and its fault record).

| From | What | Default |
|---|---|---|
| this experiment, sections 1-2 | the reworded line, the on/off lines of C2, C3 and A2, the set-buffer test hook behind its compile-time gate | gate 0: the hook is not in the binary |
| exp 0415, kit L5c (`0415-l5c-cumulative.diff`, sha256 a31ee56d) | `KYTY_BC5_ANON_SYNC`; it brings `KYTY_BC5_FRAME_STAT_WIN`, `KYTY_BC5_MAP_RECORDS=views` and `KYTY_BC5_MAP_RECORDS_CHECK_MS` | all OFF |
| exp 0412, tag nl412 (`mknl0412.py --keep-guards`, commit 45a686c4) | the learned windows removed: no file is read or written, no window is forced or mapped, a GPU fault is journaled by the catcher (always on) and nothing is added; the K1 catcher `BC5_GUARD_K1_STAT` | the removal is unconditional; `BC5_GUARD_K1_STAT` OFF |
| this experiment (`mkguards0417.py`) | `BC5_DIRECT_HEAP_GUARDS`: the 2 MiB zero guard behind each eager heap (exp 0037) | ON; `=0` makes no guard |

**The fold** (scratch clone of KytyPlus f266548; three-way `git merge` of exp 0415's tree with this experiment's,
no conflict; then the two scripts):

| Unit | 4651d1d3 | + sections 1-2 | + exp 0415 L5c (L5c alone) | + nl412 keep-guards | + the guard switch |
|---|---|---|---|---|---|
| `src/libs/bc5LleAgc.cpp` | a81efd2c | 30f9ef2b | 353893b8 (e581552a) | 457c1943 | **88f70d98** |
| `src/kernel/memory.cpp` | eff24b4c | 3844ef65 | **66b26ef5** (390f64c1) | | |
| `src/libs/libAmpr.cpp` | a2d09d32 | **1cdf1424** | | | |
| `src/bc5/load_stat.hpp`, `memory.h`, `anon_sync.hpp` | abaa375b, dd8d114a, new | | **b0637802, 224b9fa8, 058bb712** (exp 0415's, byte for byte) | | |

Both authors confirmed the folded unit (exp 0415 by count of its lines; exp 0412 by reading `learned_apply` and the
place of the switch: after nl412 only the guard loop puts entries into `g_scratch`, so the early return for `=0`
leaves nothing undone). After their confirmation one string changed (exp 0412's journal line now says the guard stays
"unless BC5_DIRECT_HEAP_GUARDS=0"); the top session waived a second reading. exp 0415's `tc` stamp and its three
`learned` counters stay as fields that read near zero, as its author asked.

**Private build** (`p0417b.sh`): normal **7ef631c3b03784b8814e07eb9a05ef89**, lean
**717aa5d69471fb1d12904c8488b88f40**; nl412 compiled at the first try; the test hook's variable name is absent from
the binary. **CPU tests on the box** (`cpu0417.sh`): semaphore off/on, set-buffer x4 (hook out), the catcher 24
checks, maprule 15281 of 15281, test0415 76 of 76 and 32 of 32, apr 33, sync 15, rec 11, anon 31: all pass.

**Runs** (`chk0417b.sh`; raw output in `raw/chk0417b-build.out` and `raw/chk0417b-runs.out`; every run 0 kernel lines
and 0 crash lines; second title RT on, no zero skip, to 240 s after G):

| Tag | What | Flips/s | Seconds with a gap over 100 ms | Longest gap | Lowest available memory | Journal |
|---|---|---|---|---|---|---|
| b1pp0, b1pd0 | ASTRO BOT 120 s, plain and `KYTY_BC5_SWITCH_DEFAULTS=0` | PASS, PASS | | | | |
| g1pon | second title, guards on (default) | 26.0 over 353 s | 60 | 852 ms | 487 MiB | "learned windows: removed" once, 0 would-learn |
| g2pon | the same | 25.5 over 352 s | 59 | 1,209 ms | 432 MiB | the same |
| l11p | lean, 120 s | PASS | | | | |
| g3poff | second title, `BC5_DIRECT_HEAP_GUARDS=0` | 26.4 over 355 s | 55 | 652 ms | 406 MiB | "removed" once, 0 would-learn, 0 timeout-fault |
| g4poff | the same | 26.1 over 354 s | 58 | 726 ms | 380 MiB | the same |

- **The lines of the code defaults are now all in a play log**, in every one of the seven starts, also with
  `KYTY_BC5_SWITCH_DEFAULTS=0`: A2 "acb state restore ... on", C1 "pending cap 64", C2 "ranges fast: on", C3 "physmap
  sorted: on", the APR line, and "the zero guards ... are on/off". (ASTRO BOT reaches A2's and C2's code within 120 s;
  section 2b's 30 s starts did not.)
- **Without the guards the route ran clean twice**: no heap-end fault in 2 x 358 s. That is this route, twice; exp
  0037's four faults were in play elsewhere, so it does not show the guards are unneeded.
- The time under the device mutex spent in the learned pass (`learned` in exp 0415's counters): 4.10 s and 3.49 s
  with the guards (2,679 and 3,018 full applications), 0.050 s and 0.053 s without (0 applications).
- Against patch 4651d1d3 on the same route (the integration's r9papr: 24.9 flips/s, 75 s with a gap, lowest
  available 338 MiB): these four runs are 0.6 to 1.5 flips/s higher, with 15 to 20 fewer gap seconds and 42 to 149 MiB
  more available memory. Single runs on different days of the same box; an observation, not a measured gain.
- The chain was stopped once before its game runs: another session's build claimed BOX-LOCK between two steps
  (09:10-09:13). Since then a chain holds one lock line for all its steps (`mklock0417.py`, `chainlock0417.inc`;
  `testlock0417.sh` 17 of 17 on the laptop). The runs above still used the per-step lock.

**Replug R9** (exp 0391's harness; private 7ef631c3, launcher 47426d8e; `s6n0391.sh` adapted to the launcher without
a learned file, `run0391.sh` takes a private build from its pins): **CLASS PASS**, mode pulls, 3 pulls, raw files
`../0413-np-session-v2-shared/integration/replug/raw/R9-*`. The harness's three pulls, all on the DualSense: closed
at t 170.5 s and reopened at 176.1 s; 211.0 s and 211.5 s; 246.8 s and 276.9 s. Its sequence ended at 09:51:48 and
it restored the default sink then ("restored: DualSense profile 1 Direct, default sink 54 Volume: 0.95"; the sink is
muted for the run by design, read back unmuted at 09:54).

**The maintainer at the box during R9** (his words through the top session; observations, not measurements):
- "Gra jest super stabilna." The first human look at a build without the learned windows.
- "Wrócił dźwięk": the harness's unmute at 09:51:48, about 305 s into the run.
- "Odłączenie i podłączenie pada działa": his own pull of the DualSense. In the log it is the close at t 359.6 s
  and the reopen on the DualSense at t 365.2 s, outside the harness's three pulls (the last ended at 276.9 s).
- "Podłączenie pada PS4 po odłączeniu ps5 też działa": the DualSense's streams closed again at t 414.7 s and were
  not reopened before the run's end at 420 s. The pad-audio log has no line for a DualShock 4 (the route opens ports
  on a DualSense only, and prints "no controller device" after 414.7 s), so his DS4 check is his observation alone;
  nothing in R9's files shows it.
- R9's own verdict is not affected: all three of its pulls ran, and were judged, before his first pull.

**Not verified in this section:** nothing of it is in the shared builds; no play by the maintainer beyond the R9
window, no run longer than G+240; `KYTY_BC5_ANON_SYNC`, `BC5_GUARD_K1_STAT`, `KYTY_BC5_MAP_RECORDS=views` and the
frame-stat windows were not switched on (their authors ran them in their own builds); the DS4 and both physical
checks on the shared binaries after the swap; the cutscene fault of the maintainer's morning play without the learned
file (a shader read of a never-written chunk) is not on this route and is what the ordered K1r fold is for.

## Open items carried from the integration (not worked on here)

| # | Item | Needs |
|---|---|---|
| 2 | NP SessionManager V2 and FW_NET return values in a title that calls them | a title or test that calls them |
| 4 | `KYTY_BC5_EVENT_COALESCE_SAME` never reached by the second title; no speed number for it or `KYTY_BC5_SEMA_TARGETED_WAKE` | exp 0415's per-phase A/B |
| 5 | `KYTY_BC5_APR_POSIX=0` ran closest to the memory wall (323, 294 with the test watchdog's kill, 258 MiB against 338 and 368 MiB with the default); five runs | given to exp 0415 and the guardian as an observation |
| 6 | the 2,799 ms gap in exp 0413's post-swap run | given to the guardian as an observation |
| 7 | the physical replug (DualSense, DS4); the maintainer's first start of `play-pkg.sh` 157021e3 on the new builds; a run longer than G+240 | the maintainer |
| 8 | exp 0414 item 3 (unbacked pages read as zero): `fault0416.py` works on the box and saw no fault in 8 runs | a run that faults; the fill is not written |
| 10 | exp 0414's survey items 3 and 5-13 | not assessed beyond the survey |

## Verdict

**The guard and the map opt-in are shown on real calls, and the next patch change (c55174b1: the learned windows
removed, exp 0415's L5c, the guard switch) builds and runs clean privately (section 7); it waits for one more fold
before the swap.** The candidate patch 33bddfa1
built privately and its hook did what was expected in six ASTRO BOT starts (section 2b); two of the new lines (C2, A2)
still have to be seen in a title that reaches their code; the CLAUDE.md diff (with the versions read on the box) and the harness self-test are done; the two other launchers
are made again from the current one and wait for the maintainer's word; the
submit-owner note has exp 0415's review: a later stage of the lock side, three counters first. Nothing here changes a
shared file.
