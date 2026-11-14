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

## 8. The K1r fold (26ef195c), its fault on ASTRO BOT, and the K1R-off form (05fe48b6) (2026-11-13 10:40-12:10)

The fold on top of c55174b1: exp 0412's rl412, K1r (two backend files, a private archive ed63df2f), the fault record,
the address watch, the probe, the first-fail catchers, the save guard, and this experiment's EOP counter
(`mkeop0417.py`, own test `mktest0417eop.py`). Kits: `mkkit0417c.py` (26ef195c, K1R and the fault record on by
default), `mkkit0417d.py` (05fe48b6, K1R off by default again).

| Candidate | Private normal / lean | Result |
|---|---|---|
| 26ef195c (K1R on) | 6cf00a3c / 6cc0b76e | builds; backend tests 121 of 121; exp 0412's CPU tests pass. **ASTRO BOT faulted 3.8 s after its start**: a GPU write (K1w) into a covered chunk of the lazy view `orbis_user_malloc`, the ring reset FAILED, the box rebooted at 11:32:18. The fault record was written (`~/bc5-data/captures/faults/20261113-113217`, the devcoredump `20261113-113218-devcd4.txt`; neither is committed). The chain's EXIT trap cannot free the lock across a reboot; the stale line was removed by hand. |
| 05fe48b6 (K1R off) | b2281fe8 / dd24ecac | builds, the same tests pass; ASTRO BOT 3 of 3 clean. Its second-title walk d4p is VOID (section 10). Its `KYTY_BC5_SWITCH_DEFAULTS=0` ASTRO BOT run left the bad save file of section 11. |

Reading of the fault (exp 0412's, not re-checked here): the cover makes the operands look mapped to the packet
filter, so a write the title would otherwise have had dropped went to a covered chunk. K1r is NOT sound on ASTRO BOT;
it leaves this fold until exp 0412's next form (cv412) is built and run on both titles. By the maintainer's rule of
2026-11-13 the fault is a bug with a record, not something to recover from.

## 9. Candidate B (27b6416f): the fold without K1r, its probe and its watch; no backend change

c55174b1 + rl412 (off) + the fault record (ON by default) with the first-fail catchers and the save guard + the EOP
counter. It links against the SHARED archive 75e30335, so a swap of B changes no backend file. Kit `mkkit0417e.py`;
private normal 3baa8e39, lean e11ad4de, both kept on the box under `~/bc5-work/exp0413/kept/`. Build and CPU tests
pass; the binaries hold no `BC5_GUARD_K1R`. Unit 8126c0aa confirmed by exp 0412's session.

Behaviour changes a swap of B would bring (for the patch notes): a GPU fault now ends the game with a record and
exit 86 instead of going on; a fault at a tagged address ends with a record before the alias-learn path; B does NOT
cure the cutscene fault of the maintainer's morning play (that is what K1r was for).

## 10. Three void runs, and the valid chain of 14:25 (`chk0417g.sh`)

The second-title walks d4p (05fe48b6, 12:00), f4p (B, 12:27) and the control f8ctl (shared fe0933c0, 12:32) all ran
into the memory wall in the menu. In all three the title left the start screen at 51-52 s, 35 s before the runner's
own cross at 87-89 s; the morning's runs stayed on it. The maintainer, asked: he pressed the pad at the start screen
and went into the game in those windows, without playing. **The three runs are void as memory measurements**: the
scripted route was out of step with the screen. Their numbers say nothing about B, the shared build or the box.

`chk0417g.sh` repeats them with the foreign input made visible: `evtest` records every key press of every joystick
during a run (the runner's keys do not pass through evdev), and the flip log gives the lowest flips/s between 50 s
and 84 s. The control must hold the start screen with no pad key, or the chain stops. Raw: `raw/chk0417g.out`.

| Run | Build | Pad keys | Lowest flips/s 50-84 s | Import at 61 s: eager / data / no view (MiB) | Available at ~60 / ~104 s (MiB) | Lowest available | Flips/s | Seconds with a gap > 100 ms, longest | End |
|---|---|---|---|---|---|---|---|---|---|
| g1ctl, walk | shared fe0933c0 | 0 | 34 | 9912 / 1216 / 8 | 947 / 911 | 366 | 26.3 | 59, 701 ms | G+240, kernel 0, crash 0 |
| g4p, walk | B 3baa8e39 | 0 | 34 | 9912 / 1226 / 10 | 932 / 863 | 298 | 25.7 | 68, 579 ms | G+240, kernel 0, crash 0 |
| g6pcut, cutscene arm, no input | B 3baa8e39 | 0 | 35 | 9900 / 1224 / 6 | 971 / 931 | 779 | 31.0 | 27, 698 ms | G+240, kernel 0, crash 0, no fault record |
| g7p, lean 120 s | B e11ad4de | - | - | - | - | - | - | - | PASS, kernel 0, crash 0 |

One run each: B's walk is within the control's spread of the morning (25.5-26.4 flips/s); 68 MiB less at the lowest
point is one pair and not a finding. The cutscene arm did not fault in this run (772 MiB under no view at 121 s, as
that arm does); one clean run does not show the fault gone.

Lesson for runs made while the maintainer is at the box: record the pad's key events beside the run, and treat a
run with a foreign key before the route's own first key as void.

## 11. The save-memory finding: the pad again, not candidate B

Seen at midday: a private ASTRO BOT save directory held a save-memory file (md5 97fb2aba, 164,965 non-zero bytes)
on which every later start ended by itself at 5 s (eboot+0x29c385), on any build; it was written by 05fe48b6 at
11:59 and again by B at 12:19, both with `KYTY_BC5_SWITCH_DEFAULTS=0`, and looked like a change of the fold.

Counts (`save0417.sh`, `save0417-list1.txt`; each pair = a fresh empty directory, 120 s, then a 30 s default start;
raw in `raw/chk0417g.out`), no pad key in any:

| Build | Words | Pairs | File | The next start |
|---|---|---|---|---|
| shared fe0933c0 | `KYTY_BC5_SWITCH_DEFAULTS=0` | 3 | 1fa391a4, 30,095 bytes, 3 of 3 | passes 3 of 3 |
| B 3baa8e39 | `KYTY_BC5_SWITCH_DEFAULTS=0` | 2 | 1fa391a4, 2 of 2 | passes 2 of 2 |
| B 3baa8e39 | defaults | 2 | 1fa391a4, 2 of 2 | passes 2 of 2 |

Both large files were written inside the window in which the maintainer pressed the pad (section 10). The test of
that (`save0417k.sh`, `raw/save0417k.out`): a cross sent at 30, 45, 60, 75 and 90 s through `KYTY_BC5_INPUT_CMD`,
no real pad key:

| Build | File after 120 s | The next default start |
|---|---|---|
| shared fe0933c0 | 97fb2aba, 164,965 bytes | ends by itself at 5 s |
| B 3baa8e39 | 97fb2aba, 164,965 bytes | ends by itself at 5 s |

**The large file is what ASTRO BOT saves once a key takes it past its first screen, and the shared build writes the
same bytes and crashes the same way.** It is not a change of the fold, and the planned bisect by pieces is dropped.
What remains is a defect of its own on every build: a first save made this way from an empty directory makes the
next start crash at 5 s. The files are kept on the box (`~/bc5-work/exp0413/n/wda/_SaveData.ks1`, `.kb1`, the two
midday ones); it is not worked on here.

## 12. Prepared, not run: candidate B's swap and its checks after the swap

`mkswap0417b.py` makes `int0417b.sh` from the integration's `int0416.sh` (pins fe0933c0 / 711d6c0d / patch
4651d1d3; `0001-new9.patch` out, `0001-new14.patch` = 27b6416f in; the archive 75e30335 must stay; the binaries must
hold B's words and must NOT hold `BC5_GUARD_K1R` or the set-buffer test hook's word). The swap is the top session's
to put to the maintainer; nothing was run on the box.

Dry run on the laptop (`dryswap0417b.sh`, `raw/dryswap0417b.out`): a stand-in HOME whose host tree is the scratch
tree with 0001-new9 applied, a stand-in `distrobox` whose "build" writes a file made of the tree's own sources, the
real patches and tree list. Three cases, 21 of 21 checks:

| Case | Expected | Result |
|---|---|---|
| ok | tree diff 27b6416f, "byte-identical to the private builds", copies kept, lock released | as expected, exit 0 |
| the build fails | both binaries and the tree (4651d1d3) restored and read back, lock released | as expected, exit 1 |
| a binary holds `BC5_GUARD_K1R` | refused by name, restored and read back, lock released | as expected, exit 1 |

Not covered by a dry run: the real build, the real binaries' words, and whether the shared binaries come out equal
to the private ones (3baa8e39 / e11ad4de).

After the swap, `post0417b.sh` (one chain, pad keys recorded, `P_N` / `P_L` = the expected shared md5s): ASTRO BOT
120 s on a fresh private test directory (the save-memory file must read 1fa391a4), the walk to G+240, the cutscene
arm, lean 120 s, and the walk once more with `BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_EOP_STAT=1` (the EOP count, never run).
Then the replug series with the maintainer at the box: `run0391.sh` with
`experiments/0413-np-session-v2-shared/integration/replug/pins0391-B-shared.env` copied over the box's
`pins0391.env`, followed by his physical DualSense replug and the DS4 (the standing audio rule). `post0417b.sh` was
checked with `bash -n` only.

## 13. ASTRO BOT's first save: reading of the SaveData path, a catcher and three candidate fixes (not run)

The defect of section 11 is on every build. What `src/libs/libSaveData.cpp` (candidate B's, 0bd91bb4) does with the
save data memory, read on the laptop:

| # | What the code does | Why it can matter here | Candidate |
|---|---|---|---|
| H1 | ONE store and one file (`sce_sdmemory/memory.dat`) for every `slot_id`; its own comment says so, and its "sync" event already names per-slot directories | a title using two slots writes one over the other at the same offsets; the next start reads the wrong slot's bytes | `KYTY_BC5_SAVEDATA_MEMORY_SLOTS=1` (new) |
| H2 | `SetupSaveDataMemory2` answers `existed_memory_size` = the store's size (2 MiB) on an EMPTY directory, unless `KYTY_BC5_SAVEDATA_MEMORY_FIXES` has "existed"; that switch is not in the default table | the title is told a save exists, reads zeros as one, and its first real save is built on that | `KYTY_BC5_SAVEDATA_MEMORY_FIXES=existed` (exp 0401 e5, exists) |
| H3 | `SetSaveDataMemory2` drops the parameters and the icon; `GetSaveDataMemory2` answers zeroed parameters and an empty icon | a title that checks them after a real save gets nothing | `KYTY_BC5_SAVEDATA_MEMORY_PARAM=1` (new) |
| H4 | none of the above: the file is right and the title's path with a real save hits another missing piece at 5 s | then the call log shows clean reads and the fault is elsewhere | the catcher's output and the crash text |

These are hypotheses from reading; no call sequence has been seen yet. The good and the bad file are on the box
(not read this round: the box was the guardian's), so the structural comparison of the two files is still owed; the
catcher gives the same information per call (slot, offset, size, non-zero count, FNV-1a).

Made, all off by default (with all off the calls do what they did): `sdm0417.inc` (the block), `mksdm0417.py`
(puts it into the unit: 0bd91bb4 -> a01e4b64, one more line in the sync path), candidate C = B + this = patch
1689b7da (`tree-candidate-C-1689b7da.md5`; the patch is in the sessions' notes folder).

- `KYTY_BC5_SAVEDATA_MEMORY_LOG=1`, the catcher: one stderr line per Setup / Get / Set / Sync.
- `KYTY_BC5_SAVEDATA_MEMORY_SLOTS=1`: slots 1-3 get their own store and file (`sce_sdmemory<n>/memory.dat`), slot 0
  keeps today's; a slot of 4 or more is PARAMETER.
- `KYTY_BC5_SAVEDATA_MEMORY_PARAM=1`: parameters and icon kept per slot (`param.bin`, `icon.bin`) and answered.

Own test (`test0417sdm.cpp` includes the block as it is, between stand-ins; `test0417sdm.sh`, VS clang++ on the
laptop): 8 of 8 cases. It shows today's overwrite with the switches off (slot 0 reads slot 1's bytes), the two
slots apart with the switch on, slot 4 refused, "existed" per slot, the parameters and icon kept across a process
and cut to the caller's buffer, and the old zeroed answers with the switch off. The unit itself has NOT been
compiled (the laptop cannot build the host); the private build is the first step on the box.

For the box, when a slot is given (about 25 minutes, CPU build then five arms of 3 minutes): `mkkit0417f.py` ->
`p0417f.sh` (the private tree from 27b6416f to 1689b7da), then `sdm0417run.sh sdm0417-list1.txt`: the catcher alone,
each candidate alone, all together; every arm is a fresh private test directory, 120 s with five scripted crosses,
then a 30 s start on what it wrote. The result wanted: which arm's next start passes, and the calls before the
crash in the arm that does not.

## 14. The swap of candidate B into the shared builds (2026-11-13 15:42-15:47) and the checks after it

The maintainer, through the top session, on "swap the shared builds to candidate B?": "Tak, podmień". Scope: the
shared normal and lean builds; the backend archive unchanged; no launcher, no desktop shortcut, no `faultrec0412.sh`
in a launcher.

`int0417b.sh` (`raw/int0417b.out`), CPU only, the box free after exp 0412's arm:

| | Before | After |
|---|---|---|
| normal `~/bc5-work/kytyplus-build/src/kyty_emulator` | fe0933c0ad7c0d9a86194bc0a7598a06 | **51af1ed78e84291caf5ee042ea82c46d** |
| lean `~/bc5-work/kytyplus-build-lean/src/kyty_emulator` | 711d6c0d33d171bcb4749903bd607aa2 | **59894428d98ed94918d09a31002c1e3b** |
| archive `libbc5_backend.a` | 75e30335 | 75e30335 |
| `~/src/KytyPlus`, diff against f266548 | 4651d1d3 | **27b6416f**, 129 patched files equal to the laptop's |

The shared binaries are NOT byte-identical to the private builds of the same tree (3baa8e39 / e11ad4de), so the
private runs of section 10 do not stand for them; the chain below is their check. Why they differ was not looked at
(the build directories differ). Undo: `~/bc5-work/exp0413/swap/kyty_emulator.before-0417b` and
`kyty_emulator-lean.before-0417b` over the two binaries, the tree by reversing `0001-new14.patch` and applying
`0001-new9.patch` (both in `~/bc5-work/exp0413/p/kit`), then a rebuild of the build directories before the next change.
`backend/kytyplus-patches/0001-bc5-lle-agc.patch` on this branch is 27b6416f (`grep -c 'exp 0372'` = 5, the route's
header present).

`post0417b.sh` on the shared builds. Its first start (`raw/post0417b-first.out`) ran ASTRO BOT 3 of 3 clean and then
stopped without starting the walk: the tag `h1` was already used on 2026-11-12, the runner refused it, and the
chain's filter hid the runner's message. A mistake of the script, not of the build; the tags were changed, the chain
now names a used tag, and it was started again 15:55-16:22 (`raw/post0417b.out`). No pad key in any run.

| Run | Result |
|---|---|
| ASTRO BOT 120 s, three in a row from a fresh private directory (twice: 6 starts) | 6 of 6 PASS, kernel 0, crash 0 |
| sw1, the walk | G+240, 25.9 flips/s, 60 s with a gap over 100 ms, longest 668 ms; 10 MiB under no view at 61 s; available 876 / 840 MiB at ~60 / ~104 s; kernel 0, crash 0 |
| sw2cut, the cutscene arm, no input | G+240, 30.7 flips/s, longest gap 574 ms; no fault, no record (one run) |
| sw3l, lean 120 s | PASS, kernel 0, crash 0 |
| sw4eop, the walk with `BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_EOP_STAT=1` | G+240, 26.6 flips/s, longest gap 747 ms; kernel 0, crash 0; **no `eop stat` line**: the counter's callback never ran in 354 s, so this route makes no chained EOP publication with a deferred callback (the journal names `BC5_R3_SUBMIT_EOP_EVENT` as on) |

Against the control of section 10 on the old shared build (26.3 flips/s, 8 MiB, 947 / 911 MiB): no difference
shown, one run each. Not explained: after three ASTRO BOT starts in a row the save-memory file reads 43703630, not
the 1fa391a4 of a single first start (both chains; the count of non-zero bytes was not taken, and every one of the
starts on it passed). Not done: the replug series on the new shared binaries and the maintainer's own start.

## 15. ASTRO BOT's first save, run (2026-11-13 16:57-17:15): the three candidates are refuted, the save path is clean

`sdmchain.sh` on the box: candidate C built privately (normal cfd35639, lean 709224df: the unit of section 13
compiles), then `sdm0417run.sh sdm0417-list1.txt`, five arms, no real pad key in any (`raw/sdmchain.out`).

| Arm | Words | File after 120 s with five crosses | The next start |
|---|---|---|---|
| sm0 | the call log only | 97fb2aba, 164,965 bytes | ends by itself at 5 s |
| sm1 | `KYTY_BC5_SAVEDATA_MEMORY_FIXES=existed` | the same | at 6 s |
| sm2 | `KYTY_BC5_SAVEDATA_MEMORY_SLOTS=1` | the same | at 6 s |
| sm3 | `KYTY_BC5_SAVEDATA_MEMORY_PARAM=1` | the same | at 6 s |
| sm4 | all three | the same | at 6 s |

What the call log shows, the same in every arm:

- one slot only (slot 0): H1 (two slots over each other) does not apply to this title;
- `existed_memory_size` answered 0 (sm1, sm4) or 2 MiB makes no difference to what is written: H2 is not the cause;
- no call passes parameters or an icon (param 0, icon 0 in every Set and Get): H3 does not apply;
- 20 Sets in the first run, at three offsets: 0 (13,397 bytes three times, then 148,267 once the keys took the title
  into the game), 393,216 (about 3.3 KiB, five times) and 1,179,648 (13,397 bytes once); the next start does one Setup
  and four Gets of 393,216 bytes at offsets 393,216, 0, 786,432 and 1,179,648, and each Get returns the non-zero
  counts that were set (3,303 / 148,266 / 0 / 13,396). **The title gets back what it stored.**

So the defect is not in the save data memory (H4). The crash itself, from the host's register dump of the failing
start (`~/bc5-work/exp0413/n/raw/sm0n-crash.txt`, not committed): a read at 0xfefdf1b58 at eboot+0x29c385, in an
instruction that indexes a stack array with `rax*8` where `eax` = 0xffffffff; the bytes before it decrement a
32-bit counter that was 0 and load `esi` = 0x2f ('/') for a call. Reading of those bytes (ours, of the dump's 64
code bytes; not checked further): the title splits a path at '/' and a count of 0 underflows. A title that has a
real save asks the host for something whose answer is a path or name, and ours is empty or has no '/'.

Next (one 30 s start on the kept directory `wda/_SaveData.sm0` with the runner's `astrolog` kind, which writes the
emulator's own call log): the host calls between the fourth Get and the fault. No fix is proposed until that is
read. The three switches stay off; `KYTY_BC5_SAVEDATA_MEMORY_LOG` did its job, `_SLOTS` and `_PARAM` have no title
that needs them (disposition: no verdict; missing: a title that uses a second slot or reads parameters back).

Also in this slot: the software replug check on the new shared normal build 51af1ed7, R10: PASS, three pulls
(`experiments/0413-np-session-v2-shared/integration/replug/raw/R10-*`). By the maintainer's rule of the same day it
was not needed (B changes no audio or pad code) and is not repeated.

## 16. The cause: `sceSaveDataTransferringMount` for another title's save (2026-11-13 18:07)

`al0417.sh al1`: one 30 s start of candidate C's private build on the kept bad directory (`wda/_SaveData.sm0`) with
the emulator's call log (`~/bc5-work/exp0413/n/raw/al1-calls.log`, 9,243 lines; it holds the title's own strings and
is not committed). The start ended by itself at 5 s with the same fault. The last host calls of the faulting thread:

    SaveDataGetSaveDataMemory2   x4      (the four reads of section 15)
    PthreadMutexInitNamed
    SaveDataTransferringMount            user_id 1000, title_id PPSA01325, dir_name sce_sdmemory

and then, before the fault, a read of 65,536 bytes of `_SaveData/PPSA21564/sce_sdmemory/memory.dat` through the file
calls. The title asks for the save of ANOTHER title (PPSA01325). `SaveDataTransferringMount` in
`src/libs/libSaveData.cpp` ignores `title_id`: it takes the directory of that name under the RUNNING title, which is
the title's own save data memory directory, creates it when it is absent, mounts it and answers OK with status
"created". The title then reads our `memory.dat` as the other title's save and faults in its own parsing (the path
split of section 15). With no key the title never has a save of its own and (not checked) does not ask.

Fix behind a switch, written and not run: `mksdt0417.py` (unit a01e4b64 -> 164c0869),
`KYTY_BC5_SAVEDATA_TRANSFER_FIX=1`: the directory is the one of the title the call names; a directory that does not
exist is not created and the call answers `SAVE_DATA_ERROR_NOT_FOUND` (0x809F0008); one that exists is mounted with
status 0. `TODO(verify)`: the console's own answer for a transfer source that does not exist. Off by default; it is
folded into exp 0419's candidate E, whose private chain has the pair for it (the kept bad save with the fix off:
the fault; with the fix on: the start must pass and name the transfer).

Dispositions of this experiment's switches: `KYTY_BC5_SAVEDATA_TRANSFER_FIX`: promote when its pair passes and one
ASTRO BOT play has gone over a first save; `KYTY_BC5_SAVEDATA_MEMORY_LOG`: diagnostic; `_MEMORY_SLOTS`, `_MEMORY_PARAM`:
no verdict (missing: a title that uses a second slot or reads parameters back); `BC5_R3_EOP_STAT`: diagnostic;
`BC5_DIRECT_HEAP_GUARDS`: no verdict (clean with and without; missing: the maintainer's play with it off);
`KYTY_BC5_SETBUFFER_TEST_HOOK`: a compile-time gate, stays 0.

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

**Candidate B (27b6416f; section 9) is clean privately and not different from the shared build fe0933c0 in the valid
chain of 2026-11-13 14:25 (section 10: one walk each, the cutscene arm, lean); the save-memory finding was the pad's
input and exists on the shared build too (section 11). K1r is out of this fold after its fault on ASTRO BOT (section
8). B is in the shared builds since 2026-11-13 15:47 (normal 51af1ed7, lean 59894428, patch 27b6416f; section 14) and its checks there are clean; the replug series on the new binaries is still to do.** The guard and the map
opt-in are shown on real calls. The candidate patch 33bddfa1
built privately and its hook did what was expected in six ASTRO BOT starts (section 2b); two of the new lines (C2, A2)
still have to be seen in a title that reaches their code; the CLAUDE.md diff (with the versions read on the box) and the harness self-test are done; the two other launchers
are made again from the current one and wait for the maintainer's word; the
submit-owner note has exp 0415's review: a later stage of the lock side, three counters first. Nothing here changes a
shared file.
