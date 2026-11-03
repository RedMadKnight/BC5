# 0388, memory cycle — J, the zero skip and shared canary slices in one private build

**Date.** 2026-11-01. **Request.** The maintainer: "Zajmij się pamięcią.", through the top session. **Status.** Prepared on the laptop; not built, because the box is taken by other experiments. Shared list, `input.cfg` and shared builds are untouched.

**Question.** Can one private build give at least 0.7 GiB of real headroom in play, with J on and the job-arena fix off? Plays 1–3 reached MemAvailable 158–324 MiB, and the slow stretches followed memory pressure.

## Levers

| lever | switch | can win | can lose |
|---|---|---|---|
| Zero skip (F541, F629) | `BC5_DIRECT_ZERO_SKIP`, set by `BC5_0388_ZERO_LIST` | 716 MiB on the bench (F629) | GPU writes into a skipped run are lost until the canary sees them, effect unknown (F542); hits came about one per several minutes in play; a device reopen imports everything at the worst moment |
| Shared canary slices (F625 lever 6), off in the play, see below | `BC5_DIRECT_ZERO_SLICES`, set by `BC5_0388_SLICES` | 84 MiB, and a check round of 0.4 s instead of 2.5 s | a hit takes back every run on the slice, about six runs; a stray write in one run is read by the others until the check |
| Scan of the other eager heaps (F625 lever 1) | `BC5_DIRECT_ZEROSCAN_AT`, set by `BC5_0388_SCAN_AT` | nothing in this play; a list for up to about 1.5 GB of heaps, gain unknown | a nice 19 thread reading each heap, up to about 2 s for the two big heaps on the bench |

Left out: the AMM pool (a per-view list is new code); narrower learned windows (a fault risk, and no breakdown exists); lean logging (it costs the journal that shows canary hits); releasing imports (F625: medium-high risk).

**The first list.** Replaced, see the end. `zero-list-moving.txt`, md5 `91d33e2e`, made by `mklist.py`: the maintainer's play scan (`zero-list-20261029-120000.txt`) intersected with the bench scan (S1), minus the three recorded canary hits (runs 22, 37, 49). 1,186 MiB in 50 runs. Hints took back about 0.4 GiB of this size on the bench, so about 0.75 GiB net of 16 MiB of slices.

**Warning, a limit on all of this.** The 20:39 tb2 play already had the skip on, on the 1.2 GB list. At 37 minutes it stood at GTT 12,639 MiB and MemAvailable 234 MiB. Whether its skip was still active then was not read. So 0.7 GiB is a bench figure, and it is not shown to survive a long play or to reach the page cache.

## How it is built and started

`box0388.sh buildm`, under the lock, with these beside it in `exp0388/s/`: `zero_skip.hpp` (from `backend/include/bc5`), `cpu_model.hpp`, `patch0388.py`, `build0388.py`, `mkunit.py`, `patch0379-bc5LleAgc.diff`, `zero-list-moving.txt`, `units.sha256`, `unitm.sha256`. Only `play0388.sh` and `sample0388m.sh` go elsewhere. Output: `exp0388/m/kyty_emulator`, keeping the name so the launcher's `pgrep -x` still sees it. Binary `1a596e50` stays where it is.

The build stops unless the tree's unit is `0a7ed551` by sha256 (md5 `29b3d8c6`, patch 0001), the unit after exp 0379's diff is `1e02ac33`, and the final unit is `2f6cb6c6`. Those two md5 come from the laptop.

```bash
BC5_0388_MEMORY=1 BC5_0388_LEARNED=$HOME/bc5-work/exp0388/direct-learned-play.txt ~/bc5-work/exp0388/play0388.sh J
```

```bash
ssh bc250 'bash -s -- 7200' < experiments/0388-job-arena-root/memory/sample0388m.sh >> samples-memory.txt
```

The sampler is exp 0379's: every 10 s, adding the emulator's and the mount's major faults to its global `pgmajfault` and per-client GTT, so the about 0.5 GiB of GTT outside the direct path gets measured (F625 lever 2).

## What was checked

- The unit rebuilt from patch 0001 has md5 `29b3d8c6`, the tree pin of `pins0381tb2r.env`. `git apply` of exp 0379's diff took it without error.
- `mkunit.py`: seven anchors, each once. The tree's file has LF line ends; a Windows `git apply` turned the laptop's copy into CRLF, caught by the build's pin.
- The whole skip block of the final unit passes `clang++ -fsyntax-only -Wall -Wextra` against exp 0379's stand-in harness. The full unit has not been compiled: that needs the box.
- `backend/tests/zero_skip_test.cpp` with a stand-in for Catch2: 91 checks pass, four new cases. Two mutants of the slice code fail (no flag check: 3 failures; runs beyond `placed`: 5). Real Catch2 was not run.
- `play0388.sh` with stand-ins: all switches, each off alone, nothing set, a missing list. The start has not been run on the box.

Not checked: whether `bc5-run.env` or `bc5-pkg.env` touches the zero switches, which needs a box read; the heap spans in the list against today's title (a mismatch is safe, the journal says `not skipped`).

**Reading the play.** First lines of the journal: `zero skip: list`, `canary BO`, `N slices`. Each minute: `MiB still skipped`, hits. Pass for this cycle: at least 0.7 GiB more MemAvailable than plays 2–3 at the same point of a play, no kernel line, and no visible glitch at a hit, on his word. Failure to gain is a result, and the warning above is the likely reason.

## Built, and what the 37-minute play changed (2026-11-01)

Binary `exp0388/m/kyty_emulator`, md5 `b975fe47`, compiled and linked on the box with the shared objects; shared binary `78f25172` unchanged before and after, `1a596e50` in place. The real Catch2 suite was still not run. Three faults showed in the build's first passes and each was stopped by a pin or a check: the laptop's `git apply` had turned its copy to CRLF (the tree's file is LF, so the two laptop md5 changed to `1e02ac33` and `2f6cb6c6`), `mkunit.py` followed that, and `box0388.sh` passed a wrong unit name.

`bc5-run.env`, `bc5-pkg.env` and `play-pkg.sh` do not touch the zero switches.

**The warning is now measured.** The journal of the 20:01–20:39 play, with the skip on the 1,218 MiB list: 460 MiB still skipped at the end. Taken back: 263 chunks by hints (526 MiB), 18 by CPU writes (36 MiB), and 11 runs by canary hits (196 MiB). Its canary still pinned 104 MiB, so the real gain at 37 minutes was about 356 MiB, not 0.7 GiB. Direct pinned was 11,772 MiB with the skip and 11,982 MiB after the reopen brought everything back.

**So two decisions changed.**

- The list drops all 13 recorded hits: `zero-list-moving.txt`, md5 `843f9fbc`, 1,014 MiB in 40 runs. This loses no real headroom, since those runs came back anyway, and it should mean fewer lost writes. Each of the 11 hits lost data until it was seen, and none of the logs shows whether that was visible.
- Shared slices are off by default. With 11 hits in 37 minutes, eight slices would have given back most of the list; the 60–84 MiB saved does not pay for that. `BC5_0388_SLICES=<n>` still turns them on.

**Expected.** About 0.6 GiB early in a play, falling toward 0.35–0.45 GiB by 30–40 minutes. That is below the 0.7 GiB aim for a long play, and these levers alone do not reach it. The scan of the other eager heaps in this play is what could add more, and its size is unknown.

## Is it a leak? (2026-11-03, the maintainer: "Głównym powodem są wycieki pamięci. Z każdą chwilą aktywnej gry pamięć RAM jest zajęta coraz bardziej")

**What the journals say**, read only from three plays, binned by 120 s of play time:

| play | direct pinned | after the load |
|---|---|---|
| 2026-11-02 18:45, 24 min | 11,362 MiB at 0, 11,568 MiB at 240 s, then 11,570 to 1,440 s | flat: no learned window, hint or zero window after 240 s |
| 2026-11-02 20:40, 14 min | 11,402 → 11,764 MiB by 480 s, 11,698–11,766 after | flat; learned and hint lines go on (16–36 per 2 min) and add 40–100 MiB each, so the title is still meeting new memory |
| 2026-11-01 23:53, 16 min | 10,612 → 11,558 MiB by 360 s, then +24 to +90 MiB per 2 min to 11,786 at 960 s | rising slowly to the end, with learned (+48–102 MiB) and hint lines every bin |

Private pinned stays 272 MiB. The BO count stays 92–105. Pinned can only grow, by design: imports are never released (F620s), so it is a high-water mark of what the title has touched. It grows while the title meets new memory (learned windows and hints), and in the 24-minute play it stopped after 4 minutes. That is the title streaming, not a host leak. The journals do not record the emulator's own heap, the mount, page cache, shmem, slab or zram, so those are open.

**The rule** (`leak0389.py`, applied per quantity of one `leak0389m.sh` record). After the load (t ≥ 600 s):

- **SUSTAINED** (a leak suspect, not proof: data kept on purpose meets it too): it rises by more than 32 MiB in each third of the rest of the play, and the last third's rise is at least half the first's. It needs 30 minutes after the load; a shorter play is OPEN.
- **STEPPED:** it grows, but one third rises under 32 MiB or the growth slows to under half: steps that stop. That fits the title streaming; it does not prove it.
- **FLAT:** the whole rise is under 64 MiB.

Judged: the emulator's anonymous memory, its shmem, its RSS plus swap; the mount's PSS plus swap; GTT; system shmem; unreclaimable slab; zram's stored data. Where it points: the emulator's anonymous memory with GTT flat means the host; shmem means memfds; slab means the kernel. Page cache is not judged, since it fills by design; MemAvailable and PSI show its cost.

**The sampler** `leak0389m.sh`: every 20 s, read only, from the laptop over ssh, waits up to 10 minutes for the emulator. The emulator's figures come from `/proc/<pid>/status` counters. `smaps_rollup` would walk its 16-GiB guest mappings under the mmap lock every 20 s and could stall the title, so there is no PSS for the emulator. The mount gets PSS. Dry run on the box against a desktop process: all fields fill.

```bash
ssh bc250 'bash -s -- 14400' < experiments/0388-job-arena-root/memory/leak0389m.sh >> leak-20261103.txt
```

```bash
python experiments/0388-job-arena-root/memory/leak0389.py leak-20261103.txt
```

## The zero-skip build for his two plays (2026-11-03)

His reading: RAM grows steadily and is not freed, and at about 14.6 GB in MangoHud the game nearly always hangs or slows. MangoHud's RAM figure is, as far as I know its source, MemTotal − MemAvailable in GiB (TODO(verify): read `src/memory.cpp` of the installed MangoHud). This box's MemTotal is 15,192 MiB = 14.84 GiB, so 14.6 GiB used means about 250 MiB available: the floor every sampler has seen (158–324 MiB). His point is where the box sits at its limit. The leak sampler will say whether it rises to that limit and stays, or steps up with the scenes.

**Build.** `exp0388/z/kyty_emulator`, md5 `902585e2492dd30f5ebba8bfb54cf8c0`. It is today's shared normal (`4d2b1b1d`, no J, the job-arena fix on) with one private unit: `bc5LleAgc.cpp` with exp 0379's zero skip and the slice switch (`patch-z-bc5LleAgc.diff`). The diff went on with fuzz; its reopen line landed inside a lambda and was moved by hand back to the device-reopen block. Linked with the shared objects. The skip block passes the stand-in harness; the box compile had no error.

**Switch.** `BC5_DIRECT_ZERO_SKIP=<list>`, off when unset; `BC5_DIRECT_ZERO_SLICES` stays unset (one canary slice per run). List `exp0388/m/zero-list-moving.txt`, md5 `843f9fbc`, 1,014 MiB in 40 runs, all 13 recorded hits left out.

**Expected headroom** with the skip on: about 0.6 GiB early in a play, falling to 0.35–0.45 GiB by 30–40 min as hints take runs back (the 37-minute play of 10-31 kept 460 MiB skipped of 1,218, less a 104-MiB canary). If the heap spans differ from the list's, the journal says `not skipped` and the gain is 0.

**The two plays**, same binary, his saves, `input.cfg` unchanged, with the leak sampler running:

```bash
~/bc5-work/exp0388/play0389z.sh off
```

```bash
~/bc5-work/exp0388/play0389z.sh on
```

The first line it prints must name the binary `902585e2`, the list `843f9fbc` and the launcher `97835f88`. The skip's own lines in the journal: `zero skip: list`, `MiB skipped`, `canary hit`.

**What it can show.** One play each, in scenes that may differ, with the skip able to lose GPU writes, neither confirms nor refutes his reading of a leak as the cause of the hangs. If the hangs and slowdowns come later or not at all with the skip on, that is a hint for more headroom, not proof. The useful measure is the sampler's avail and PSI against the moment of each event. Risk with the skip on: GPU writes into a skipped run are lost until the canary sees them, visual effect unknown, about one hit per several minutes.

**Review (Codex, 2026-11-03).** A sum whose part was not read now stays unknown (`-1`) instead of becoming a number; the labels are SUSTAINED and STEPPED, with their limits in the output. `test_leak0389.py` covers both unknown cases and a good sum.

## The off play's hang, and is clutter the cause? (2026-11-03)

**Off play** (skip off, 08:40–08:49, ring timeout at t 567, reset succeeded). The rule gives OPEN: under 600 s. Nothing grew after the load (GTT 12,482 → 12,526 MiB from t 145, emulator anon 102–191, mount ~720, unreclaimable slab 294). Avail was about 400 MiB from t 103 to the hang (387 lowest), memory PSI 0.4 % just before it. No GPU page fault from that process. The hang: the gfx ring with no waves and the CP standing on a `WAIT_REG_MEM` (dword 1411 of dcb #432913) for a label to equal 1, the label holding a pointer-like value instead; two label writes of the paired acb were dropped by the host. A GPU-side wait, not a memory symptom in this record.

**The maintainer's hypothesis:** "Im bardziej zaśmiecona pamięć tym szansa na zawieszenie wzrasta". The sampler now records fragmentation: the Normal zone's free memory from `/proc/buddyinfo`, in blocks of ≥ 64 KiB and ≥ 2 MiB, the unusable index for 2 MiB (‰), and the compaction and migration counters. `/proc/pagetypeinfo` and debugfs's `extfrag_index` are root-only on the box (not in the sudoers list), so the index is computed from buddyinfo. A read on the boot of 08:53, minutes into a play: 65 MiB free in Normal, 0 MiB in 2-MiB blocks (unusable 1000 ‰), 179 compaction stalls, 10.9 M failed page migrations: full fragmentation at the 2-MiB level arrives within minutes of a fresh boot.

**Hangs since 10-31** (11; boot age at the play's start, t of the hang; the play start is the emulator's first journal line):

| hang | boot age | since last reset/boot | t | outcome |
|---|---|---|---|---|
| 10-31 17:04 | 40.1 h | 40.1 h | 205 s | machine down |
| 10-31 20:39 | 2.9 h | 2.9 h | 2247 s | reset |
| 11-01 07:22 | 14.0 h | 10.5 h | 839 s | reset |
| 11-01 07:41 | 14.4 h | 0.1 h | 823 s | reset |
| 11-01 07:54 | 14.7 h | 0.1 h | 397 s | reset |
| 11-01 23:12 | 2.1 h | 2.1 h | 356 s | machine down |
| 11-02 00:11 | 0.7 h | 0.7 h | 1073 s | machine down |
| 11-02 08:34 | 8.2 h | 8.2 h | 478 s | machine down |
| 11-02 20:56 | 12.1 h | 12.1 h | 950 s | reset |
| 11-03 08:49 | 24.1 h | 11.7 h | 567 s | reset |
| 11-03 08:53 | 24.2 h | 0.0 h | 192 s | machine down |

The two shortest (205 and 192 s) are on the oldest boots, and boot age against t correlates at −0.54. But n is 11, that is not significant, a 2-hour boot also hung at 356 s, and the builds, scenes and players differ across these days. After a reset the median t is 567 s, the first hang of a boot 714 s; both spans overlap fully. Only hangs are counted: plays that did not hang are missing, so this is not a hazard per minute. **The data cannot decide.**

**The smallest controlled test.** Same build (the shared normal, skip off), same save and the scripted route, so that the scene and input are the same, the new sampler running:
- A: right after a reboot, desktop up, `drop_caches`, play at once.
- B: same boot after an hour of uptime that includes one full play that ended normally (no reset).
Measure t to the first hang (or 40 minutes) and the fragmentation fields at the hang against the same fields at the same t in the other arm. One pair cannot decide with t spread from 192 to 2247 s; three pairs per arm is the least that can show a large effect. Cheaper and on every play: compare the sampler's fragmentation and compaction counters in the minute before each hang with all other minutes; if hangs do not stand out there, clutter is not their trigger.
