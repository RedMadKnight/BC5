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

**The guard and the map opt-in are now shown on real calls; the rest is prepared.** The candidate patch 33bddfa1
built privately and its hook did what was expected in six ASTRO BOT starts (section 2b); two of the new lines (C2, A2)
still have to be seen in a title that reaches their code; the CLAUDE.md diff (with the versions read on the box) and the harness self-test are done; the two other launchers
are made again from the current one and wait for the maintainer's word; the
submit-owner note has exp 0415's review: a later stage of the lock side, three counters first. Nothing here changes a
shared file.
