# 0413 — NpCppWebApi SessionManager V2 into both shared builds

## Question

The ten NpCppWebApi SessionManager V2 NIDs keep "coming back" as missing. Is that a regression, and can they go into
both shared builds for good?

The maintainer, 2026-11-12: "NpCppWebApi - to już było kilka razy dopisywane - znowu był regres i to usunąłeś?", then
"tak przenies i zbuduj - sprawdz przy okazji inne elementy które nigdy nie weszły, a które były testowane".

## History (why it looked like a regression)

| When | What | Where it went |
|---|---|---|
| exp 0328 | AnyPS5's NpCppWebApi port, 136 entry points | patch 0001, shared builds (F393, 77c1ce2c) |
| exp 0329 | the rest of the second title's missing imports, 197 → 10 | patch 0001, shared builds (F393) |
| exp 0402 | names the last ten: SessionManager V2, missed by 0328's port (F809) | analysis only, no code |
| exp 0401 series e | `mknp0401.py` adds the ten behind `KYTY_BC5_NP_SESSION_V2`, **default off** | private builds `exp0401e…` only |

Patch 0001 on main had 0 of the 10, so every build from it lacked them. Nothing was removed; they never reached the
shared builds, and even the private builds needed the variable set.

## Setup

- Base: KytyPlus f266548 (`refs/Coder787-source_KytyPlus`, `git -c core.autocrlf=false archive`) plus main's patch
  0001. `git diff f266548` reproduces main's patch byte for byte: 7e7c6899 with the index lines removed.
- `mknp0413.py` runs `mknp0401.py`'s edit unchanged on `src/libs/libNpCppWebApi.cpp` (exp 0328's unit, md5 7c40b784),
  then makes it **on by default**: the ten are registered unless `KYTY_BC5_NP_SESSION_V2=0`. One stderr line at
  registration:
  - `[bc5] NpCppWebApi SessionManager V2 on (10 exports registered)`
  - `[bc5] NpCppWebApi SessionManager V2 off (KYTY_BC5_NP_SESSION_V2=0, the loader's stubs)`
- Output unit md5 910acbb5. Candidate patch 0001 md5 2dbed49a (a43378ca without index lines). It differs from main's
  only in that file's hunk (+81 lines). Exp 0372's route is intact (5 lines, the header present).
- `int0413.sh`: the swap on the box, modelled on exp 0389's `int0388j.sh`:
  - an atomic BOX-LOCK claim;
  - pins checked first;
  - copies of both binaries and the unit;
  - the unit swapped in;
  - `ninja kyty_emulator` for normal and lean (the backend archive is not rebuilt and must not change);
  - checks that both binaries carry the "on" line and all ten NIDs and that the tree's diff equals the candidate;
  - a restore on any failure.

  Pins in `pins0413.env`, filled from the step-1 read.

## Result

The top session's GO: step 1 at 10:00, step 2 at 10:02. Each box step was guarded (no emulator, no foreign lock).

**Step 1 (reads, 10:01).**
- Shared normal 4d2b1b1d, lean 30d4be33 and archive 75e30335 are exp 0389's pins. The unit was 7c40b784.
- The tree's diff without index lines read 4d186f67, not the 7e7c6899 given in the request, so the step stopped and was
  reported.
- Cause: the laptop's value went through Git Bash's grep, which strips CRs, and the patch has 14,834 CR bytes (CRLF
  host sources).
- The full diff fetched from the box is byte-identical (`cmp`) to main's patch 0001, md5 728f2a77 on both sides.
- The top accepted this and set the pin to 4d186f67. Added to LESSONS R45.

**Step 2 (the swap, 10:03:10–10:03:32, `int0413.sh` from `~/bc5-work/exp0413/s/`).**
- The lock was claimed by hard link and released at the end.
- Ninja rebuilt the one unit and relinked: normal 10 s, lean 11 s.

| | before | after |
|---|---|---|
| normal `~/bc5-work/kytyplus-build/src/kyty_emulator` | 4d2b1b1d | **f6445dc6** |
| lean `~/bc5-work/kytyplus-build-lean/src/kyty_emulator` | 30d4be33 | **30ee854b** |
| archive `libbc5_backend.a` | 75e30335 | 75e30335 (not rebuilt) |
| `~/src/KytyPlus/src/libs/libNpCppWebApi.cpp` | 7c40b784 | 910acbb5 |
| tree diff vs f266548 | main's 0001 (728f2a77) | candidate (2dbed49a) |

The script's checks passed:
- both binaries changed and the archive did not;
- each binary holds the "on" line once and all ten NIDs;
- the tree's diff equals the candidate patch.

Three warnings in each build:
- `libNpCppWebApi.cpp:50` (`-Winvalid-noreturn`) and `:62` (an unused constant), both in exp 0328's code above the new
  block;
- `stringUtils.h:321` (deprecated `wstring_convert`).

None comes from the new lines. No emulator was started. `~/bc5-work/exp0412` was not touched.

**Rollback.** Copy back `~/bc5-work/exp0413/swap/kyty_emulator.before-0413` and `kyty_emulator-lean.before-0413` over
the two binaries, and `libNpCppWebApi.cpp.before-0413` over the unit. Then rebuild before the next change, since the
build directories' objects are the new ones. A rollback without touching files: `KYTY_BC5_NP_SESSION_V2=0`.

**Not verified here:** the ten functions at run time. Series e's `npgate0401` gate ran on private builds only. The
title's calls go through the maintainer's play.

## Verdict

The ten SessionManager V2 NIDs are in both shared builds and in patch 0001 on this branch (2dbed49a), on by default. They
no longer depend on a private build or a variable. A run-time check in play is still to come.

## Audit: other tested items never integrated

The maintainer also asked to check the other items that were tested but never integrated. `audit-unintegrated.md`
(read-only, laptop) lists 67 rows with file:line evidence. Nothing from exp 0390 on is in patch 0001; the last patch
commit on main is a8324c8b (exp 0389). 28 rows are recommended for integration default on, 20 default off, 19 left out
(failed, answered catchers, or no measured gain). Each integration needs the maintainer's yes (D19).

## Integration of the tested private builds (2026-11-12, branch int/0413-tested-into-shared)

The maintainer: "przepisuj po kolei to co było zrobione u nas i merge do main, a potem poprawki z emufive". The top
session set the source and the rules:
- the source is the guardian's daily line fast7/lean7;
- one commit per item, in the audit's order;
- default-on only with a clean measured result.

**Source.** Binaries g412v bc4356a5 (fast7) and g412L2 8ef2168f (lean7). Every private source was copied from the box at
10:2x–10:33 (reads only, the top's GO). The main GPU unit follows the lean unit 8f6e92b3 = g412d + the fixed poll, as the
guardian asked. g412v's ten catchers and the refuted `BC5_GUARD_NOGPU_UNPIN` stay out.

**Replay (`integration/replay.py`, `runner.py`).**
- 52 steps from the shared tree (f266548 + 0001 2dbed49a): every edit script with the box's arguments, in build order
  (0401 series c/e/e3/e4–e8, 0409, e11, 0412 g412d/e/memfast/L2).
- 51 are byte-exact against the files the private build compiled (`steps.tsv`, `final-vs-box.tsv`). None was made by hand.
- The exception is step 22's `libNpCppWebApi.cpp`. It is a fold of e8's FW_NET edit (e613bc8f) with this experiment's V2
  unit (910acbb5): e613bc8f's head plus 910acbb5 from line 816. The fold's diff from e613bc8f equals 935fcc7e→910acbb5
  exactly. It had never been compiled.
- g412v's eleven left-out steps were replayed on a side copy, byte-exact to 3cea62bc (`vchain.tsv`).

**Commits.**
- 51 step commits (step 04 changes no file).
- One commit for the defaults table `src/bc5/switch_defaults.hpp`: `setenv(name, value, 0)` from a priority-101
  constructor in `main.cpp`. A value in the environment wins, `NAME=0` restores a row's old behaviour, and
  `KYTY_BC5_SWITCH_DEFAULTS=0` skips the table.
- One commit per audit row turning its switches on: A2–A9, A11–A22, B16, C1–C3 (`defaults.py`). That is 55 switches,
  each checked to be read in the sources.

**Off in code, set by the launcher only:**
- the zero skip and its poll;
- the orphan release (30 s), split and forget;
- `CP_COHER_START_DELAY` (never A/B'd).

**Off:** `NOGPU_UNPIN`, `SET_PREDICATION`, PRT/extra AMM commands, the catchers, the journals, and the e11 reset
switches (they never acted).

Final patch 0001: md5 76c1d045, 85,516 lines.

**Not yet done:** the box build of both shared builds, then 0389's checks:
- S6N route, RT on;
- lean start;
- ASTRO BOT start (also the condition for A11's TLS default);
- the replug check for the audio rows A5, A17, A19 (s6n0372.sh + replug0372.sh).
Then the shared launchers' words, and the merge.

### Private build and checks (2026-11-12 10:59–11:45, the top's GO, slot to 12:30)

**Build.** `integration/p0413.sh` built patch 76c1d045 under `~/bc5-work/exp0413/p` only:
- A copy of `~/src/KytyPlus` (with `.git`, which ffmpeg-core's CMake asks for its commit), 0001 2dbed49a reversed and
  76c1d045 applied. All 121 patched files match the laptop's tree.
- Configured as `bc5-build.sh` configures. The shared backend paths were only read; the cached `ffmpeg-94dde08.zip` was
  copied in, so nothing was downloaded.
- Results: normal a76f86abffed99a3423ce5c9a394d5f4 (284 warnings), lean f64dadd2c39dd9fcffd90564eb72be5a (287 warnings).
  None of the warnings is in `switch_defaults.hpp` or `main.cpp`. `libNpCppWebApi.cpp` has only its two old warnings.
- The archive stayed 75e30335.
- Both binaries carry the NP V2 "on" line, the ten NIDs, `KYTY_BC5_SWITCH_DEFAULTS`, the C1–C3 switches, `FW_NET` and
  `AMM_SCATTER`. Step 22's fold compiles.

**Static checks (the top's points a and b).**
- No switch is read before the priority-101 constructor. The only namespace-scope `getenv` initialiser is `BC5_GC_MODE`
  in `bc5LleAgc.cpp`, which is not in the table and runs at the default priority. The other constructors are the lean
  cleanup (101, different names) and hostMenu's MangoHud constructor (default priority).
- The backend archive has no namespace-scope `getenv` initialisers.
- Nothing starts a thread at or before priority 101.

**Runs.** All RT on, `ulimit -c 0`, the kernel log streamed to the laptop. The second title ran from exp 0412's named
snapshot, copied privately.
- The second title used `integration/run0413p.sh`, derived from 0412's `run0412n.sh` by `mkrun0413.py`, with the
  launcher words of `integration/words0413.txt` and the fuse at 13,000/2,048.
- The lean and ASTRO BOT starts used `integration/start0413.sh`.

| run | what | result |
|---|---|---|
| p1def | normal, defaults on | PASS: gameplay at 118 s, then 120 s of walk, 24.5 flips/s, 60 s with a gap over 100 ms, longest 758 ms. 0 kernel lines, 0 crash lines. The journal shows acb restore on, quiet journal on, events cap 64, physmap sorted, NP V2 and 37 port lines "on" |
| p0off | normal, `KYTY_BC5_SWITCH_DEFAULTS=0` (point c) | PASS: gameplay at 127 s, +60 s, 23.2 flips/s, longest gap 2,893 ms. Only NP V2 (on in code) prints "on"; acb restore and TLS read "off": the old behaviour is reachable |
| l2lean | lean, 150 s, no input | PASS: 216 MiB anon at the end, defaults on, 0 kernel or crash lines (l1lean did not start: 0412's launcher refuses `BC5_LEAN=1`; the lean binary strips the diagnostics itself) |
| a1astro | ASTRO BOT, defaults on | **CRASH at 5 s**: a write to address 0 at guest 0x90000048f, a stack-guard prologue taking a null out-pointer |
| a2astro | `KYTY_BC5_TLS_FIXES=0` | the same crash: not A11 |
| a3astro | `KYTY_BC5_SWITCH_DEFAULTS=0` | PASS 120 s |
| b1–b9, c1–c6 | rows set to 0 in groups | the same crash, at the same address, whenever four or more of A15, A16, A17, A21, A22 are on. It passes with any two of them off (c3–c6, b5) and does not depend on the other rows |
| d1 | A15, A16, A17, A21, A22 off | PASS 120 s |

**Consequence.**
- A15, A16, A17, A21 and A22 are taken back out of the defaults table, one commit each (`integration/undefault.py`). They
  are the SaveData memory/Http2/pad-open-ext, Json2/Ult/UserService/SystemService, AudioOut/AudioIn/Ngs2,
  firmware-pad and dead-table rows: 20 switches.
- The proposed `play-pkg.sh` diff turns them on for the second title, as the daily line ran them.
- Patch 0001 is now a2ab53c7. It differs from the built 76c1d045 only in the table's rows; the d1 run is that table's
  behaviour, through the environment.
- The cause in ASTRO BOT is not found: its start depends on how many of these ports are on, not on one of them.

**Not done yet:**
- the replug check (`s6n0372.sh` + `replug0372.sh`, A5 and A19 being audio). It needs exp 0391's runner adapted to a
  private binary: the next slot;
- a rebuild from a2ab53c7, which comes with the swap;
- his play.

### Second round of checks (2026-11-12 11:47–13:33, the top's slot to 13:15; overrun by about 3 minutes, see below)

**ASTRO BOT's crash, separated (the top's points 1a–1c), on the private binary a76f86ab:**

| run | setup | result |
|---|---|---|
| e1env | table off; the 20 switches of A15/A16/A17/A21/A22 in the real environment | PASS 90 s |
| e2env | table off; all 56 switches in the real environment | PASS 90 s |
| e3env | table on; those 20 in the real environment (so `setenv` adds only the other 36) | PASS 90 s |
| e4dum | table on (all 56 through `setenv`) plus 20 dummy variables in the starting environment | PASS 90 s |

- **1c, the crash state.** The guest reads its stack guard through the GOT (not `fs:0x28`) and gets the right value
  0xdeadbeef00000007. It then crashes on `mov [rsi], rdx` with `rsi = 0`: the function's second argument, an output
  pointer, is null. The address (eboot+0x48f), the registers and the log lines before it are the same in every crash.
  The host backtrace was not taken.
- **Reading at that point: a layout effect of `setenv` at start.** The defaults were moved into the initial environment
  through one re-exec of the binary:
  - commit 5a495769, executing `/proc/self/exe`;
  - commit 5544da9e, executing the real path instead. Through `/proc/self/exe` the process was named `exe`, so
    run p2def's harness saw no emulator and left it running. It was stopped by hand: our process, our run.

**Rebuilds.** Incremental, in the private tree with `p0413b.sh` and `p0413c.sh`. Final private binary from patch
1150799b: normal d1b6f9cb, lean 5767f015. Both carry the re-exec and the ten NIDs; the archive is unchanged.

| run | binary, setup | result |
|---|---|---|
| p3def | d1b6f9cb, 36 rows through the re-exec | PASS: gameplay at 118 s + 120 s, 25.8 flips/s, longest gap 628 ms; the emulator's environment holds `KYTY_BC5_SWITCH_DEFAULTS_EXEC=1` |
| f2lean | 5767f015, 150 s | PASS |
| f1astro | d1b6f9cb, defaults through the re-exec (A15–A22's five rows already off) | **CRASH at 6 s, the same address** |
| g10, g25, g36 | d1b6f9cb, table off, plus 10, 25 or 36 dummy variables | PASS each, 60 s |
| p4full | d1b6f9cb, table off, all 56 switches as launcher words (`integration/words0413full.txt`) | PASS: gameplay at 117 s + 120 s, 25.8 flips/s, longest gap 582 ms |

**Verdict of this round.**
- ASTRO BOT's start crashes when the integration's switches are on as defaults, through `setenv` and through the re-exec
  alike.
- It passes with the table off at every environment size tried.
- The daily line ran these switches only with the second title, so the crash is their combined effect on ASTRO BOT.
  Its cause is not found.
- Therefore the table is emptied (commit fa3e09ec, patch 040812ce). Every switch becomes a launcher word of the second
  title only (`integration/play-pkg-0413.diff`, made by `mkpkg0413.py` from `words-integration.txt`: 56 words; a value
  already in the environment wins). That is exactly the tested p4full configuration.
- The re-exec code stays, with no rows.

**Replug check (point 2): not done.**
- The replug harness is exp 0391's, copied to `integration/replug/`:
  - the box directory renamed to `exp0413r`;
  - the binary pinned to d1b6f9cb, the launcher to 97835f88;
  - the dropped `COMPUTE_RING=-1` anchor removed;
  - the 56 switches passed as words, with the table off;
  - the disk limit 90 % (the box was at 86 % with 72 GB free).
- R2 lost its ssh connection at the start step and gave the lock back.
- R3 started at 13:31, past the slot. The shared `play-pkg.sh` stopped at once ("No package at …/game.pkg": the game is
  unpacked now and that launcher has no `BC5_GAME_DIR`). No emulator, no GPU work; the lock was released by the run
  itself.
- The derived launcher needs the `BC5_GAME_DIR` edit before the next try.

### Third round (2026-11-12 13:35–13:47, the top's slot to 15:00)

**Build.** Incremental rebuild to patch 040812ce (empty defaults table): normal e82e65479c5f6dd70d919114374c61f4, lean
4c75bbc7746f29fbf05e86d63c3d0f58. The archive stayed 75e30335.

**p5final.**
- **Setup:** e82e6547, the second title with the 63 launcher words of `integration/words0413launch.txt` (the proposed
  launcher's words), RT on.
- **Gameplay** at 118 s, then a GPU hang at 173 s. `gfx_0.0.0` ring timeout, the ring reset succeeded, the box stayed up.
  The runs stopped there, as the rule requires.
- **Class:** the devcoredump `20261112-134445-devcd3.txt` reads `GRBM_STATUS` 0xa0407028, `CP_STALLED_STAT2` 0x18000,
  ME 0x77b, PFP 0xea1, no page fault. That is F403's signature (a compute dispatch that does not end), as in his plays on
  the private and shared builds.
- **Timed-out buffers:** acb #134489 and dcb #134490 (26 dispatches, 13 indirect). Dumps are under
  `~/bc5-data/captures/play-20261112-1341/gc/`.
- **Not a regression from a single run.** p4full ran the same configuration on d1b6f9cb without a hang, and F403 hits
  the daily line too.
- **Not done:** ASTRO BOT, lean and the replug on e82e6547. The replug harness now has the `BC5_GAME_DIR` edits
  (`integration/gamedir.py`).

### Fourth round (2026-11-12 13:48–13:57): back to a2ab53c7's table through setenv; ASTRO BOT still crashes; no swap

**Branch.** The top session's decision: the five rows A15/A16/A17/A21/A22 are launcher-only, every other row stays on
by default through the plain `setenv` constructor, and the re-exec is dropped. Commit 5d71c985 restores patch a2ab53c7.

**Build.** Private and incremental, `p0413e.sh`: normal f61d5874ec7e776db502a827579d7be2, lean fd0af8a0. The archive is
unchanged.

**h1astro.** ASTRO BOT on f61d5874 with the plain defaults: **CRASH at 5 s**, at the same guest address 0x90000048f.

**What the d1 pass was.**
- d1 delivered "five rows off" as 20 `NAME=0` words in the environment.
- Those 20 extra entries in the starting environment are what e4dum showed to be enough by themselves to pass (20 dummy
  variables, all rows on).
- So d1 did not show that the 35-row table is safe for ASTRO BOT. Here is what does hold:

| configuration | result |
|---|---|
| table off (any size of environment tried) | ASTRO BOT passes |
| rows as words in a larger starting environment (e1env–e4dum, d1, c3–c6, b2/b3/b5/b7) | ASTRO BOT passes |
| rows through `setenv`, or through the re-exec, with nothing else added (a1, b1, b4, b6, b8, b9, c1, c2, f1, h1) | ASTRO BOT crashes |

- The common factor is a layout or timing effect around start that these switches tip. The cause in ASTRO BOT is open:
  which host call returned just before eboot+0x48f, and with what, is the next question.

**Consequence.** By the top's rule, no swap. The shared builds stay f6445dc6 and 30ee854b. Not run on f61d5874: the
second title, lean, the `=0` start, the replug.

**Zero skip in the second-title runs (the top's question).** Every second-title run of this experiment had the zero skip
on with its poll: p1def, p0off, p3def, p4full and p5final. Each took `BC5_DIRECT_ZERO_SKIP` from exp 0412's own list
(`~/bc5-work/exp0412/zero-list-0412.txt`, 1,010 MiB in 2 heaps; p5final's journal shows 740 MiB of RenderGpuWcLarge
skipped) plus `BC5_GUARD_ZSKIP_POLL_SUBMIT=1`. `~/bc5-work/zero-list-pkg.txt` does not exist.
- The zero skip has three GPU hangs in exp 0412's history, and a zeroed input can also produce a dispatch that never
  ends.
- So p5final's F403 reading is weaker than stated above: the hang may be the zero skip's.
- The zero skip is out of the proposed `play-pkg.sh` diff.

### ASTRO BOT's crash: the root-cause work (2026-11-12 13:58–14:1x; private diagnostic builds only)

**Tool.** `integration/mkwalk0413*.py` add a crash walk to a private copy of `runtimeLinker.cpp` (tree a2ab53c7,
aba94c24), behind `BC5_0413_CRASH_WALK=1`. It logs:
- the guest frame chain;
- each call site's 64 bytes;
- the key and the table of the faulting lookup;
- each import stub's hops to its target.

The bytes were disassembled with clang/llvm-objdump (VS's LLVM on the laptop). ASTRO BOT's eboot is a SELF whose
segments are neither plain nor zlib, so its code was read from the running process instead. The private tree and
binary are back to aba94c24 / f61d5874 afterwards.

**The chain at the fault** (runs w1walk–w4walk; the crash is unchanged with the extra variable):

| frame | return address | what |
|---|---|---|
| — | 0x90000048f | the fault: the function's first store, `*arg2 = arg3`, with `arg2 = NULL` |
| 0 | 0x900000454 | a wrapper at 0x900000435: `mov rsi, [rsi]`, so it hands on the *value* of its pointer argument |
| 1 | 0x90029930a | a loop over 24-byte entries up to an end pointer; per entry, `cmp(key r14, [rbx+8], 0x400)` through import 0x90001d750; on a match it passes `rbx+0x18`, the next entry's first field, to the wrapper |
| 2 | 0x9002a0ebd | calls the frame-1 function right after a call through stub 0x9074b62e0 |
| 3–5 | 0x9010d29fe, 0x90029fdeb, 0x9000000af | up to the title's entry |
| 6 | 0x56515544ebad | **host**: the host's call of the guest entry |

**State at the fault.**
- The key string (frame 1's `r14`) is **empty**.
- **Every table entry around the match is zero**: 15 entries, all four fields 0.
- The compare is a **host** function (import index 0x62d, reached through stub 0x9074bc310). For ("", entry name
  NULL) it returned "equal", so the title took the next entry's NULL as a string pointer.
- Stub 0x9074b62e0 is not the host's: it lands in guest code at 0x9200040c0 (another loaded guest module, a SIMD
  routine).
- A host heap pointer (0x5577…) sits in a guest callee-saved register (frame 1's saved `r15`).

**Reading so far (inference).** The title walks a table that should hold its entries and finds it zeroed, with an empty
key. Two places to look next:
1. **The host compare's contract for a NULL argument.** It treats ("", NULL) as equal. The console's libc would crash
   or compare differently. Which NID is index 0x62d, and what does our body do with NULL?
2. **Why the table range covers zeroed entries.** Either the end pointer or count comes from a host call that is
   switched by these rows, or a host write that fills the table is skipped. That would explain the dependence on the
   rows and on the environment's size.

The top's discriminator, `-ftrivial-auto-var-init=pattern` and `=zero` builds (`pz0413.sh`), is in progress.

**Discriminators (2026-11-12 14:04–14:24), ASTRO BOT starts on private builds of a2ab53c7:**

| test | result |
|---|---|
| `-ftrivial-auto-var-init=pattern` build (fd867ac6), plain defaults | the same crash: eboot+0x48f, `rsi = 0`, write to address 0 (z1pat) |
| the same build plus 20 dummy variables | PASS 60 s (z2pat) |
| f61d5874, one extra variable `BC5_PAD` of 0, 1, …, 8, 12, 16, 24, 32, 48, 64 characters | crash in all 15 (s0pad–s64pad) |
| f61d5874, n dummy variables `BC5_DUMMY_nn=1` | n = 2, 4, 6: crash; 8, 10, 12, 16, 20, 24: PASS; 29: crash; 32: PASS (c2cnt–c32cnt) |

- **Not an uninitialised host local.** The pattern fill changes neither the fault address nor the dependence on the
  environment. The `=zero` build was not made.
- **Not byte alignment of the initial stack.** The length of one variable does not matter.
- **It follows the number of environment entries, and not monotonically.** b1's crash with 29 `NAME=0` entries
  repeats as c29cnt. That looks like a layout effect of the pointer array's size (the initial `envp`, and the block
  `setenv` moves it to), not of the data.
- **With the table off, every start passed** (a3astro, g10, g25, g36), so the switches being on is still a needed
  condition.

**Open, for the next session.**
- Which import is index 0x62d (the compare), and what does its host body do with a NULL argument?
- Who owns guest memory 0x300a80000–0x300a83000 (the zeroed table and the empty key)? Is it a host mapping that a
  switched-on path returns earlier, larger, or at another address?
- An in-emulator log of host calls before the fault is the tool for both; it was not built in this slot.

**Note from exp 0412 (2026-11-12).** The maintainer's lean7 play of this morning hung the GPU at 107 s (07:52:07 gfx ring
timeout, the reset succeeded; shared notes `exp0412-lean7-hang-0752.md`). That was g412L2 8ef2168f with the zero skip
and its poll. So the lean unit 8f6e92b3 is verified here only as source text ("g412d + the poll"), not as a clean
line. The cause is unknown; the zero skip is one candidate, as in p5final. It stays off in code and out of the proposed
launcher diff.
