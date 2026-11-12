# 0416 — EmuFive items as switches, and the later round of exp 0413, in one build

**Question.** The maintainer (2026-11-12): "zainstaluj zmiane lauchera a potem zmiany emufive". Which of exp 0414's
items can go into patch 0001 as default-off switches now, and do they, with the three changes exp 0413 left for "a
later round", build and run without changing anything while they are off?

**Status: built privately and run on the box 2026-11-12 (Result below); not in the shared builds.** Result and
Verdict were added after the private build.

## Setup

Branch `exp/0416-emufive-switches` on main `f1795ac0` (patch 0001 01abfc0c = the shared builds, normal ce0e3b92, lean
35ec3341). KytyPlus f266548. All edits are made by scripts on pinned inputs (`mk0416.py`, `mk0416x.py`); patch 0001
becomes **a099e662**, five files change.

| Change | File (md5 in → out) | Switch | Default |
|---|---|---|---|
| Codex's EOP ownership fix (its `audit/eop-owned.cpp.diff`, taken as written): `r3gpu_submit_eop` no longer uses a global ring of 4,096 packets that a deferred soft-CP replay read by raw address; the replay owns a copy | `src/libs/bc5LleAgc.cpp` 8f6e92b3 → 777eb681 | none (it only changes who owns six dwords); `BC5_R3_SUBMIT_EOP_EVENT` stays a switch and is still not a default | — |
| Set-buffer's map flavour is opt-in | `src/libs/libAmpr.cpp` ddf52b7b → 9a526e31 | `KYTY_BC5_AMM_SETBUFFER_MAP=1` | off: a call with the map signature is the buffer flavour (one line for the first 16); exp 0413's guard stays in front |
| The pure fixes leave the behaviour table: A2 `BC5_DIRECT_ACB_STATE_RESTORE`, C1 `KYTY_BC5_EVENT_PENDING_CAP=64`, C2 `KYTY_BC5_RANGES_FAST`, C3 `KYTY_BC5_PHYSMAP_SORTED` | `src/bc5/switch_defaults.hpp` 852f4d03 → 4f704194 | each still `NAME=0` | on, and `KYTY_BC5_SWITCH_DEFAULTS=0` no longer skips them (table `kFixes`) |
| EOP trigger with the same data as the newest unread entry only counts on it (exp 0414 item 1b; the idea is KytyPS5 c86d31b) | `src/graphics/host_gpu/renderer/sync.cpp` 06c1349c → 2d97421c | `KYTY_BC5_EVENT_COALESCE_SAME=1` | off |
| A semaphore signal wakes only the waiters it hands counts to: one condition variable per waiting thread (exp 0414 item 5; the idea is KytyPS5 a0268f1; F451's convoy) | `src/kernel/semaphore.cpp` 3aa9c8b4 → 81049581 (CRLF file) | `KYTY_BC5_SEMA_TARGETED_WAKE=1` | off |

The two KytyPS5 commits were read in exp 0414 (GPL-2.0, clean provenance); the code here is written against our own
units, no text is copied.

**Not code in the emulator:**
- `fault0416.py`, the catcher for exp 0414's ray-tracing hypothesis (item 3): beside a run it reads the kernel log and
  writes, for each amdgpu page fault, the GPU address and whether the emulator process has anything mapped there
  ("unmapped" is the hypothesis' case). Logging only: no fill, no backend change, the archive 75e30335 is not rebuilt.
- `DESIGN-submit-owner.md`, a design note for item 4 (the submit-owner thread). No code.

## Checked on the laptop

- **Targeted wake, CPU test** (`mktest0416.py` cuts the semaphore class and its methods out of the edited unit and
  compiles them with stand-ins; VS clang++ 22, `-std=c++20 -O1 -Wall -Wextra`; run with the switch unset and `=1`).
  Both runs: PASS, 0 failed checks (about 48 s each).
  - T1, 8 waiters and `Signal(3)`: exactly the first three return. The five that got nothing were woken 10 times in
    all with the switch off (the broadcast) and 5 times with it on (once each, by the signal that serves them).
  - T2 priority order; T3 3,000 rounds of timed waits against signals: signalled 5,964 = handed out 5,964 + left 0,
    both ways; T4 cancel (6 waiters, all `Canceled`); T5 delete (4 waiters, all `Deleted`); T6 80,000 signal/wait
    pairs with the poll interval stretched to 10 s: no stall.
- **EOP ownership**: Codex's own CPU test (`audit/run_eop_owned_test.cmd`: the old code fails, the fixed code passes
  10,000 deferred values and 40,000 from 8 threads). Not re-run here.
- **`fault0416.py --test`** on `experiments/0016-direct-first-submits/raw/d-run27-dmesg.txt`: 4 fault blocks at one
  address, the client line and the ring timeout are read.
- Not checked on the laptop: that the five units compile in the host (the box build does that).

## Planned box checks (the top's list)

Private build first (`p0416.sh`: the private tree from 01abfc0c to a099e662, normal and lean). Then, on those binaries:
ASTRO BOT start with each new switch on and off (the guard line must still be there); the second title, RT on, no
zero skip, 240 s after G, switches off and on; `BC5_R3_SUBMIT_EOP_EVENT=1` once with the ownership fix; one start with
`KYTY_BC5_SWITCH_DEFAULTS=0` (the four fixes must still read as on); `fault0416.py` beside the second-title runs.

## Result

Box, 2026-11-12 21:00-21:30 (the top's slot), private build only (`chk0416.sh`; raw logs stay on the box under
`~/bc5-work/exp0413/n/raw`, tags below; `chk0416.out` beside them). Kernel 7.2.11-ogc4.1 as recorded.

**Build.** All five units compile; patch a099e662 on the private tree gives normal
**37e3bae63e9e7df1bd9ecf610a75595f** and lean **465f86bebccec4161c295045ab872c59** (285 warnings in the lean log, not
compared with the build before). The shared builds were not touched (ce0e3b92, 35ec3341 re-read after the runs).

**ASTRO BOT, 30 s starts on the normal build** (PASS = ran 30 s, 0 kernel lines, 0 crash lines):

| Tag | Words | Result | Switch lines in the log |
|---|---|---|---|
| a1x0 | none | PASS | pending cap 64 |
| a2x0 | `KYTY_BC5_EVENT_COALESCE_SAME=1` | PASS | COALESCE_SAME on; pending cap 64 |
| a3x0 | `KYTY_BC5_SEMA_TARGETED_WAKE=1` | PASS | TARGETED_WAKE on; pending cap 64 |
| a4x0 | both and `KYTY_BC5_AMM_SETBUFFER_MAP=1` | PASS | both on; pending cap 64 |
| a5x0 | `KYTY_BC5_SWITCH_DEFAULTS=0` | PASS | pending cap 64 (fix C1 stays on without the table) |
| a6x0 | `BC5_R3_SUBMIT_EOP_EVENT=1` | PASS | pending cap 64 |
| a7x1, a7x2, a7x4, a7x6 | 1, 2, 4, 6 dummy variables | PASS x4 | — |
| a8x0 | `KYTY_BC5_AMM_TRACE=1` | PASS | 3 set-buffer calls, a4 = 0x9088e4e98, 0xd, 0x300a82bc0 |

**The second title, RT on, no zero skip, 240 s after G, normal build, `fault0416.py` beside:**

| Tag | Switches | Flips/s | Seconds with a gap over 100 ms | Longest gap | Kernel / crash lines | Page faults caught |
|---|---|---|---|---|---|---|
| r1off | off | 24.5 over 357 s | 85 | 1,640 ms | 0 / 0 | 0 |
| r2on | COALESCE_SAME, SEMA_TARGETED_WAKE, SUBMIT_EOP_EVENT on | 24.2 over 356 s | 101 | 1,897 ms | 0 / 0 | 0 |

One run each way: the differences are inside what single runs of this route have shown and say nothing about speed.

**Lean build**, l5lean, the two switches on, 120 s: PASS, 0 kernel lines, 0 crash lines.

**Not exercised, said plainly:**
- **The set-buffer guard and the map opt-in.** In this binary the leftover a4 of the title's first set-buffer call is
  0x9088e4e98, not -1 (a8x0), so no call had the map signature in any of the 11 starts: neither exp 0413's line nor
  the new "exp 0416: set-buffer" line was printed. The top's condition "the guard line must still be there" is
  therefore **not met and not refuted**; the code path is the one exp 0413 proved on 0eda68b5 and ce0e3b92, with one
  more condition behind it. A call with a4 = -1 needs a test of its own (a stand-in call, or a build where the
  leftover happens to be -1).
- **`KYTY_BC5_EVENT_COALESCE_SAME` in the second title.** Its "on" line is printed at the first trigger that finds the
  event already triggered; r2on and l5lean have no such line, so the title never reached that path in these runs.
  ASTRO BOT reaches it (a2x0, a4x0).
- **A2, C2 and C3 with `KYTY_BC5_SWITCH_DEFAULTS=0`**: they print no line; only C1's line shows the fix table works.
- `fault0416.py` saw no amdgpu page fault, so its "mapped / unmapped" answer was not produced; the ray-tracing
  hypothesis of exp 0414 stays open. (The kernel's last ring timeout is from 19:07, before this slot.)
- Speed of either switch (0415 measures them per phase in its own build), a long session, the physical replug.

**Launchers.** `~/bc5-work/play-pkg.sh` is 157021e3 since 19:20:25 (exp 0413's `instpkg0413.sh`; the old one is
`play-pkg.sh.before-0413`). `play-pkg-log.sh` and `play-pkg-quiet.sh` were not changed and now differ from it: no
`ulimit -c 0`, no unpacked-title handling, none of the 20 title switches. The new `play-pkg.sh` has not had a real
start on the shared build yet.

## Verdict

**Builds and runs; the switches are safe to carry default-off, with one check missing.** Patch a099e662 compiles in
both configurations; with everything off both titles run as before; each new switch on starts ASTRO BOT and, for the
semaphore switch and the EOP fix with `BC5_R3_SUBMIT_EOP_EVENT=1`, runs the second title 240 s with RT without a
kernel or crash line. Missing before a shared build: a test that drives set-buffer with a4 = -1 on mapped and on
unmapped memory in this patch (guard line, opt-in line), because chance did not produce the call here. Nothing from
0416 is in the shared builds; that needs the top's release and Codex's short round.

## Addendum 2026-11-12, after Codex's round (laptop only; Result and Verdict above are unchanged)

Codex's entries of 17:43 and 22:20 UTC (`coordination/codex-to-claude.md`) asked for three things. No box run was made.

**1. The missing set-buffer test** (`mktest0416sb.py`). The five real functions are cut out of the edited
`libAmpr.cpp` (9a526e31, the unit of patch a099e662) and compiled with stand-ins (VS clang++ 22, `-std=c++20 -O1 -Wall
-Wextra`): a table of committed and reserved ranges for the kernel's query, a recorder for the map, a real header for
the buffer flavour. Six calls (A, B: a4 = -1 and 0xffffffff on ASTRO BOT's committed heap page; C: a4 = -1, nothing
there; D: a4 = -1, reserved only; E: a3 == va; F: a4 = 0x9088e4e98) and 40 repeats of A, in four processes:

| Guard | `KYTY_BC5_AMM_SETBUFFER_MAP` | A, B (mapped target) | C, D (not mapped) | Lines exp 0413 / exp 0416 | Result |
|---|---|---|---|---|---|
| on (default) | off (default) | attached, nothing mapped | attached, nothing mapped | 16 / 2 | PASS |
| on | 1 | refused by the guard: attached | mapped, 0x4000-rounded, prot 0x33 | 16 / 0 | PASS |
| `=0` | off | attached, nothing mapped | attached, nothing mapped | 0 / 16 | PASS |
| `=0` | 1 | mapped (exp 0413's bug, behind two switches) | mapped | 0 / 0 | PASS |

E and F attach in every run without a line; the 40 repeats never map unless the guard is off and the opt-in on. So
the check that the box runs could not make is made on the function's own text. What it is not: the real
`KernelVirtualQuery` and the real `ExecuteAmmMapCommand` are stand-ins, and no title made the call.
One wording fault seen: with the guard off, the exp 0416 line says "a target that is not mapped" for A and B too.
The patch is left as built (a099e662); the wording is for the next patch change.

**2. `fault0416.py`, the stream** (R11/R46). The boundary is now the newest kernel stamp of the log before the run
(one `dmesg`), and the followed stream is filtered by stamp, not by arrival time; a reader thread feeds a queue, so the
limit and a signal are obeyed in silence; the dmesg child is closed, ended and reaped in `finally`, also on SIGTERM,
SIGINT and SIGHUP. `test0416fault.py`, synthetic, 17 checks, PASS on the laptop: silence (a 1.2 s limit ends after
1.5 s with no line), a late old backlog (dropped), a new fault at the first moment (kept), the reader's end, repeats,
the pin, the cleanup of a child. Codex's repro `audit/test_fault0416_stream.py` cuts out `fresh()`, which no longer
exists, so it does not run against the new file.

**3. The labels** (R13). A sample is now "CPU VMA now: present / none / unknown" with the PID and the sample time;
the file's header says what a sample cannot show (backing, the GPU's page table, a read of zeros). Each fault line
carries "run attribution: unknown". The process is pinned (`--pid`, or the first `kyty_emulator` seen, start time
checked against PID reuse) and never re-pinned. `chk0416.sh` counts "CPU VMA now: none" instead of "unmapped".
The Result's words "mapped / unmapped" above describe the old file, which caught nothing.

**Not verified:** the new catcher has not run on the box: the Linux parts (signals, `sudo` ending a root `dmesg`,
`/proc` maps, the pin at a real start) are untested; the laptop skipped the own-process maps check (no `/proc`).
`chk0416.sh` was edited and only syntax-checked.

The two new switches stay experimental; no speed claim is made for them.

**Second round, Codex 22:43 UTC (R46), laptop only.** Three faults in the catcher of the round above, fixed:
- `end_child` closed the stream first; with a silent child the reader holds the buffer lock in its read, so the close
  never returned and the child was never ended (Codex's `audit/test_fault0416_silent_cleanup.py`: rescue needed after
  0.8 s). Now: end the child, wait with a limit, join the reader with a limit, close the stream only after the reader
  has ended; if something still holds the pipe the last line says "INCOMPLETE cleanup" and nothing blocks. Codex's
  repro now passes (0.002 s, no rescue). My earlier test used a child that wrote every 50 ms and did not cover silence.
- A failed one-shot `dmesg` gave boundary -1 and would have kept the whole old backlog. Now a failed or stampless
  first read follows nothing and writes "MONITOR ERROR" (exit 2).
- The header said kept lines "belong to this run"; it now says they are stamped after the boundary and that the run
  they belong to is unknown.
`test0416fault.py`: 23 checks, PASS (a writing child, a silent child, a grandchild that holds the pipe, the failed
first read). Still not run on the box; on Linux the case "sudo cannot be signalled" is expected to end as
"INCOMPLETE cleanup", which is untested.
