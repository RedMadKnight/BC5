# 0416 — EmuFive items as switches, and the later round of exp 0413, in one build

**Question.** The maintainer (2026-11-12): "zainstaluj zmiane lauchera a potem zmiany emufive". Which of exp 0414's
items can go into patch 0001 as default-off switches now, and do they, with the three changes exp 0413 left for "a
later round", build and run without changing anything while they are off?

**Status: written and checked on the laptop; not built, not run on the box yet.** This file gets its Result and
Verdict after the private build.

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

Pending.

## Verdict

Pending.
