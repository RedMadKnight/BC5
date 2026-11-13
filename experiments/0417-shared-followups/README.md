# 0417 — follow-ups to the shared builds of 2026-11-13 (patch 0001 4651d1d3)

**Question.** After the integration of exp 0416 + 0415 + 0412 (`../0416-emufive-switches/integration/README.md`), which
of its open points can be closed or prepared on the laptop, without the box, so that the next slot and the next swap
are short? The top session's list of 2026-11-13: the wording of one line, a line for the silent code defaults, a hook
that forces set-buffer's a4 = -1 on a real call, the two other launchers, CLAUDE.md, the replug harness's self-test,
the submit-owner note to exp 0415.

**Status: laptop work done; nothing of it is built on the box, nothing is in the shared builds.** The patch on main
stays 4651d1d3 (it must match the shared builds, D19).

## Setup

Branch `exp/0417-shared-followups` on main `7d21b208`. KytyPlus f266548 with patch 4651d1d3 as the pinned input.
Laptop: VS clang++ 22 for the CPU tests (`-std=c++20 -O1 -Wall -Wextra -D_CRT_SECURE_NO_WARNINGS`).

## Result

### 1. The next small patch change (`mk0417.py`; rides with the next swap, not its own)

Candidate patch 0001 **c61fe48b** (126 files; 4651d1d3 plus `0417-on-4651d1d3.diff`, 155 lines; sums of all patched
files in `tree-candidate.md5`). The full candidate is not in the repository (the repository's line-ending rule would
change it outside `backend/kytyplus-patches/`); it is made by `mk0417.py` on the pinned units, and a copy lies in the
sessions' shared notes as `exp0417-0001-candidate-c61fe48b.patch`.

| Unit | In -> out | Change |
|---|---|---|
| `src/libs/libAmpr.cpp` | a2d09d32 -> 1cdf1424 | exp 0416's line no longer says "a target that is not mapped" when exp 0413's guard is off; it says the guard did not take the call. The test hook (below), compiled out. |
| `src/bc5/setbuffer_test.hpp` | new -> 56589d82 | `KYTY_BC5_SETBUFFER_TEST_HOOK 0`: the hook's compile-time gate |
| `src/kernel/memory.cpp` | eff24b4c -> 3844ef65 | `KYTY_BC5_RANGES_FAST` (C2) prints "exp 0412 ranges fast: on/off" once at its first use; `KYTY_BC5_PHYSMAP_SORTED` (C3) now also prints "off" |

**What a log shows for `KYTY_BC5_SWITCH_DEFAULTS=0` after this change** (the code defaults of `kFixes` must stay on):
C1 "exp 0412 events: pending cap 64" (play log, exists), C2 "exp 0412 ranges fast: on" (play log, new), C3 "exp 0412
physmap sorted: on" (play log, exists; "off" is new), the APR row "exp 0415: APR reads by pread ..." (play log,
exists), A2 "exp 0401: acb state restore (exp 0381) on" (the journal, exists; not in the play log, and the lean build
has no journal lines). A2 was left as it is: its line exists, in the journal.

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

**Proposed box check for the next slot** (private build of c61fe48b with the header set to 1, ASTRO BOT 30 s each):
`mapped` (guard line, PASS), `unmapped` (exp 0416's line, PASS), `unmapped` with `KYTY_BC5_AMM_SETBUFFER_MAP=1` (the
hook's result line; PASS expected whatever the map returns), and once `KYTY_BC5_SWITCH_DEFAULTS=0` for the lines of
section 1.

### 3. `play-pkg-log.sh` and `play-pkg-quiet.sh`

**Not done: the two files are not on the laptop or in the repository.** They need one read on the box. Then
`../0413-np-session-v2-shared/integration/mkpkg0413.py <file> words0413pkg.txt <out>` (the generator that made
`play-pkg.sh` 157021e3; every anchor asserted) is tried on each; where an anchor differs the edit is written for that
file. The result is two diffs for the maintainer's word, not an install.

### 4. CLAUDE.md

`CLAUDE-md-update.diff` (applies on main 7d21b208 with `git apply`): the kernel is 7.2.15-ogc1.1.fc45 (the replug
runner's line on 2026-11-12 and 2026-11-13); Mesa and libdrm are marked "to re-read" (not read since); the shared
builds' paragraph names patch 4651d1d3, its code defaults and the two exp 0412 switches that must stay unset; the
launcher 157021e3; the Wayland socket was `wayland-1`. Not applied here: the top session merges it.

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

**Prepared, not proven.** The patch change and the hook pass their CPU tests on the laptop and wait for a private
build; the CLAUDE.md diff and the harness self-test are done; the two launchers wait for a read on the box; the
submit-owner note has exp 0415's review: a later stage of the lock side, three counters first. Nothing here changes a
shared file.
