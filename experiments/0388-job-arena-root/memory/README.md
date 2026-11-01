# 0388, memory cycle — J, the zero skip and shared canary slices in one private build

**Date.** 2026-11-01. **Request.** The maintainer: "Zajmij się pamięcią.", through the top session. **Status.** Prepared on the laptop; not built, because the box is taken by other experiments. Shared list, `input.cfg` and shared builds are untouched.

**Question.** Can one private build give at least 0.7 GiB of real headroom in play, with J on and the job-arena fix off? Plays 1–3 reached MemAvailable 158–324 MiB, and the slow stretches followed memory pressure.

## Levers

| lever | switch | can win | can lose |
|---|---|---|---|
| Zero skip (F541, F629) | `BC5_DIRECT_ZERO_SKIP`, set by `BC5_0388_ZERO_LIST` | 716 MiB on the bench (F629) | GPU writes into a skipped run are lost until the canary sees them, effect unknown (F542); hits came about one per several minutes in play; a device reopen imports everything at the worst moment |
| Shared canary slices (F625 lever 6) | `BC5_DIRECT_ZERO_SLICES`, set by `BC5_0388_SLICES` | 84 MiB, and a check round of 0.4 s instead of 2.5 s | a hit takes back every run on the slice, about six runs; a stray write in one run is read by the others until the check |
| Scan of the other eager heaps (F625 lever 1) | `BC5_DIRECT_ZEROSCAN_AT`, set by `BC5_0388_SCAN_AT` | nothing in this play; a list for up to about 1.5 GB of heaps, gain unknown | a nice 19 thread reading each heap, up to about 2 s for the two big heaps on the bench |

Left out: the AMM pool (a per-view list is new code); narrower learned windows (a fault risk, and no breakdown exists); lean logging (it costs the journal that shows canary hits); releasing imports (F625: medium-high risk).

**The list.** `zero-list-moving.txt`, md5 `91d33e2e`, made by `mklist.py`: the maintainer's play scan (`zero-list-20261029-120000.txt`) intersected with the bench scan (S1), minus the three recorded canary hits (runs 22, 37, 49). 1,186 MiB in 50 runs. Hints took back about 0.4 GiB of this size on the bench, so about 0.75 GiB net of 16 MiB of slices.

**Warning, a limit on all of this.** The 20:39 tb2 play already had the skip on, on the 1.2 GB list. At 37 minutes it stood at GTT 12,639 MiB and MemAvailable 234 MiB. Whether its skip was still active then was not read. So 0.7 GiB is a bench figure, and it is not shown to survive a long play or to reach the page cache.

## How it is built and started

`box0388.sh buildm`, under the lock, with these beside it in `exp0388/s/`: `zero_skip.hpp` (from `backend/include/bc5`), `cpu_model.hpp`, `patch0388.py`, `build0388.py`, `mkunit.py`, `patch0379-bc5LleAgc.diff`, `zero-list-moving.txt`, `units.sha256`, `unitm.sha256`. Only `play0388.sh` and `sample0388m.sh` go elsewhere. Output: `exp0388/m/kyty_emulator`, keeping the name so the launcher's `pgrep -x` still sees it. Binary `1a596e50` stays where it is.

The build stops unless the tree's unit is `0a7ed551` by sha256 (md5 `29b3d8c6`, patch 0001), the unit after exp 0379's diff is `0cf48cd9`, and the final unit is `86768672`. Those two md5 come from the laptop.

```bash
BC5_0388_MEMORY=1 BC5_0388_LEARNED=$HOME/bc5-work/exp0388/direct-learned-play.txt ~/bc5-work/exp0388/play0388.sh J
```

```bash
ssh bc250 'bash -s -- 7200' < experiments/0388-job-arena-root/memory/sample0388m.sh >> samples-memory.txt
```

The sampler is exp 0379's: every 10 s, adding the emulator's and the mount's major faults to its global `pgmajfault` and per-client GTT, so the about 0.5 GiB of GTT outside the direct path gets measured (F625 lever 2).

## What was checked

- The unit rebuilt from patch 0001 has md5 `29b3d8c6`, the tree pin of `pins0381tb2r.env`. `git apply` of exp 0379's diff took it without error.
- `mkunit.py`: seven anchors, each once. Line ends are CRLF.
- The whole skip block of the final unit passes `clang++ -fsyntax-only -Wall -Wextra` against exp 0379's stand-in harness. The full unit has not been compiled: that needs the box.
- `backend/tests/zero_skip_test.cpp` with a stand-in for Catch2: 91 checks pass, four new cases. Two mutants of the slice code fail (no flag check: 3 failures; runs beyond `placed`: 5). Real Catch2 was not run.
- `play0388.sh` with stand-ins: all switches, each off alone, nothing set, a missing list. The start has not been run on the box.

Not checked: whether `bc5-run.env` or `bc5-pkg.env` touches the zero switches, which needs a box read; the heap spans in the list against today's title (a mismatch is safe, the journal says `not skipped`).

**Reading the play.** First lines of the journal: `zero skip: list`, `canary BO`, `N slices`. Each minute: `MiB still skipped`, hits. Pass for this cycle: at least 0.7 GiB more MemAvailable than plays 2–3 at the same point of a play, no kernel line, and no visible glitch at a hit, on his word. Failure to gain is a result, and the warning above is the likely reason.
