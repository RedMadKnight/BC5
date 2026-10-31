# 0385 — The night lake's holes on the merged build: does F486's coverage hold on a run with holes

**Status: plan only.** Written on the laptop on 2026-10-31, before any box access. Nothing below has run. Findings, if any,
take numbers from F720 (range F720–F739, given by the top session).

**Question.** F486 called the holes coverage ("where a hole forms, no writer drew") from one episode: 14 finals in K3,
median 7.4 % of the lake window, with K2 hole-free. On the merged shared build, RT on, in a run with holes (mean shot
patch ≥ 20 %):
1. Do the holes' edges still ignore the 8×8 tile grid?
2. Do the frame's compressed writes still miss the tiles that end as holes?

**What this answers in Q21, and what it does not.** Q21 asks what decides the state. This experiment does not answer that,
in any outcome. It tests the step F486 took between coverage (a) and metadata (b), and so decides where the next Q21
experiment looks: at the writers' input (the culling or occlusion input, F350), or back at the metadata.

## Decision rule, fixed before the runs

All numbers come from `raw/<tag>.tz.txt`. Each final has `holes H mixed true T shifted Z`; each consecutive pair has
`hole tiles A drawn tiles B`. A **hole final** has H ≥ 0.01. A **qualifying run** has a mean shot patch ≥ 20 %, no fault,
and its RT proof (below). Medians are taken over one qualifying run's hole finals and pairs.

| Outcome | Condition | Meaning |
|---|---|---|
| **Confirmed** | ≥ 30 hole finals and ≥ 7 pairs; \|median(Z − T)\| ≤ 0.05 with median T > 0.02; median A ≤ 0.01 with median B ≥ 0.10 | F486 holds on a full hole run and loses its "one episode" limit. Q21's next step stays on the writers' input (F350). |
| **Overturned** | ≥ 30 hole finals and ≥ 7 pairs; median T ≤ 0.02 with median Z ≥ 0.10 (whole tiles), or median A ≥ 0.05 (writes reach hole tiles) | F486 is corrected by a new row. Reading (b) returns, and the next experiment reads the HTILE state at decompress #2. |
| **Inconclusive** | A qualifying run that meets neither row | The numbers are recorded with no claim. |
| **No verdict** | No qualifying run in three | F486 stands as it is, with the same limits. Shorter episodes are reported, not counted as confirmation. |

Reference values: K3 T 0.368, Z 0.367, A 0.000, B 0.153–0.182. The self-test gives T 0.000, Z 0.991 for tile-aligned holes
and T 0.821, Z 0.823 for cells. The HTILE's 8×8 granularity stays TODO(verify), as in F486.

**Not measured:** whether the fix package changed the holes. There is no arm on the old build. Of the five RT-on lake runs
on record, two reached 20 %: W1 32.2 (exp 0355), K1 31.4 (exp 0365); H1 9.7 (exp 0362), K2 9.2, K3 9.9 (exp 0369). At that
rate, assuming independent runs, three runs give about a 78 % chance of a qualifying run, and three clean runs would
happen 22 % of the time. So a clean series says nothing about the fixes.

**Also recorded, at no extra box time:** the burst pattern per run (`<tag>.bursts.txt`) against the holes, since K2 mostly
lacked the +8.4 ms burst; the patch per shot; flips per second.

## Build state (from the top session's message and the repo; the box was not read)

- **Binary:** shared normal build `~/bc5-work/kytyplus-build/src/kyty_emulator`, md5 78f25172. Its archive is 3292bdaf. The
  lean build 7b246487 is not used, because each run's RT proof reads the journal, which lean compiles out.
- **Source:** `cand/port-np-libc` fab8660 (D19 finished 12:40:53; both RT-on smokes passed, startup evidence only). Main is
  d6fa368 until its fast-forward, so this branch starts from origin/main and carries no build change.
- **Changes since K1–K3's build 1000ad2a that this repo records:** among them the NP and libc fixes (F740, F741),
  `BC5_DIRECT_REBASE_DISPATCH` removed (F765), lean's list (F766), `=0` meaning off for seven switches (F767). The run sets
  none of those switches (`ENVX` is empty).
- **Launcher:** `play-pkg.sh` was 55531ab6 at the last read, on 2026-10-30. **Whether D19 changed it is not known here.** `setup0385.sh`
  stops if it differs, and then the five edits must be derived again before any run.
- `pl`, `sn`, `tz` and `ana` read no journal. The bench's `journal:` line reads `direct.log`, and F766 changes lean only.

## Plan

**Runs.** At most three, tags **K4, K5, K6**, in that order. Each is exp 0369's lake bench unchanged: `ab0385.sh <tag> <saves>
'' 330`, the poller beside it (`pl0385.py <tag> 85 … 212 2.0 6`), one GPU workload. The series stops at the first run with a
mean shot patch ≥ 20 %.

**Length.**

| Step | Time |
|---|---|
| Take, copy the kit, setup, self-test | ~1 min |
| One run: ab ~5:05–5:16 (K2, K3), analysis and clean-up ~0:35 | ~6 min |
| Release | ~0:30 |
| **Total** | **~7.5 min if K4 has holes, ~20 min for all three** |
| **Hard bound** | **30 min**, the lock line's "until" |

The bound: each run sits under a box-side `timeout -k 10 540`, each emulator under a cap at SECS + 60 = 390 s, and the
kernel stream ends itself after 32 min at the latest.

**RT and the lake's reflections.** RT on in every run, nothing skipped:
- `input-0385.cfg` has `RayTracing.PPSA03671=on`; `ab0385.sh` stops if it does not.
- The launcher derives from today's `play-pkg.sh`, which has `BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-0}`, so the
  reflection traversal (0x11d049aa00, 0x11d04a6000, 0x11d04bb900) and the BVH compaction (0x909974400) run (exp 0382's
  README, read on the box for 55531ab6). `ENVX` is empty, so no run adds a skip list.
- This differs from the lake runs of exps 0194–0295, whose copied launcher carried a four-program skip list and had
  reflections off.
- **Proof per run:** the `journal:` line in `<tag>.out` must show 0 ray-tracing-off lines and no skip lines, as K3's did. A
  run that shows either is not RT on and does not qualify.

**Save copy.** `~/bc5-work/saves-lake-1153`, the maintainer's lake save, as in K1–K3. `bench0385.sh` resets the private copy
`~/bc5-work/exp0299/wd/_SaveData/PPSA03671` from it when they differ, and the launcher runs in that private working directory,
its save directory beside it. The live saves are compared only, never restored over: pin **52ee672646ca6087**, C locale (`LC_ALL=C sort -k2`, added to
`ab0385.sh`, since the box's default pl_PL gives a different sum for the same saves).

**Stop rules.** Any of these ends the series at once:
- A kernel fault, ring timeout or reset line (ab exit 1), or a machine-down. No analysis runs and nothing is deleted.
- Live saves differ from the pin, before or after a run: ask the top session.
- A foreign lock line, a `MAINTAINER PLAYING` line, or an emulator that is not ours.
- The binary is not 78f25172, or the launcher is not the pinned one.
- `/var/home` at 80 % or more (K-runs write ~2.7 GB of snapshots, deleted after each run).
- A classifier refusal of any box step: reported to the top session, never worked around.

A run lost to a route failure counts as one of the three. The series is not extended.

**Written on the box:** `~/bc5-work/exp0385/`, `~/bc5-data/priv/exp0385/<tag>` (snapshots), the private save copy above, the
private journal under `~/bc5-data/captures/play-*`, and our BOX-LOCK and BOX-QUEUE lines. Nothing shared is written. No shot
or snapshot is viewed; they are deleted unviewed after each run's analysis, and journals stay private.

## Changes from exp 0369's K2/K3

- **Same:** the bench, poller, analysis, launcher derivation, input configuration, save copy and route.
- **`mkkit0385.py`** derives the kit from exp 0369's with the number replaced. A diff against 0369 shows one header line per
  file and the `ab0385.sh` changes below.
- **`ab0385.sh`:** the box-side cap and the C-locale saves sum.
- **`run0385.sh`** (new): one run from guard to clean-up on the box, so one plain ssh carries it. It survives a dropped ssh
  through `tee -p`.
- **`kstream0385.sh`** (new): the kernel stream, ending itself when our lock lines are gone.

**Checked on the laptop (stand-ins, no box):** all scripts parse; `tz0385.py --selftest` passes; `run0385.sh` took the right path
for a normal run, ab stopping at once, a foreign lock line, our lock line gone, a different binary, an emulator up, a failed
analysis, a late kernel line, changed live saves, a dropped reader and a hung poller; the cap stops an emulator that outlives
it and ends quietly with one that does not. Not checked before the slot: anything on the box, including `setup0385.sh`, the
files it needs from exps 0299, 0347 and 0353, and the route on this build.

## Commands, in order, after the top session's slot

Each is one plain command, in the forms the maintainer's allow rules cover. From `experiments/0385-lake-holes-repeat`.

1. **Take** (guard first, the first thing that touches the box):
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'cd ~/bc5-work || exit 1; pgrep -a "^kyty_emulator" && { echo "an emulator runs: stop"; exit 1; }; [ -e BOX-LOCK ] || touch BOX-LOCK; [ -s BOX-LOCK ] && { echo "locked:"; cat BOX-LOCK; exit 1; }; [ -e exp0385 ] && { echo "exp0385 exists: stop"; exit 1; }; S=$(cd _SaveData && find PPSA03671 -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); [ "$S" = 52ee672646ca6087 ] || { echo "live saves $S: stop"; exit 1; }; b=$(md5sum < kytyplus-build/src/kyty_emulator | cut -c1-8); [ "$b" = 78f25172 ] || { echo "binary $b: stop"; exit 1; }; mkdir exp0385 && echo "water session exp 0385 | series K4-K6, lake bench, RT on, build 78f25172 | start $(date +%H:%M) | until ~$(date -d +30min +%H:%M)" >> BOX-LOCK; echo "exp 0385, water session, Q21: the lake bench K4-K6, RT on, build 78f25172 | $(date "+%F %T")" > exp0385/CLAIM.txt; echo "water exp 0385 | claimed: the lake bench K4-K6, RT on, build 78f25172, up to 30 min | $(date "+%F %T")" >> BOX-QUEUE; md5sum play-pkg.sh | cut -c1-8; uname -r; df --output=pcent /var/home | tail -1; cat BOX-LOCK'
   ```
2. **Kit:** `scp setup0385.sh ab0385.sh bench0385.sh ana0385.sh run0385.sh kstream0385.sh bt0362.sh pl0385.py sn0385.py tz0385.py swz0248-z4.json bc250:bc5-work/exp0385/`
3. **Setup and self-test:**
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'cd ~/bc5-work/exp0385 && chmod +x run0385.sh kstream0385.sh && bash setup0385.sh && distrobox enter ubuntu -- python3 -I tz0385.py --selftest swz0248-z4.json'
   ```
4. **Kernel stream,** in the background, kept running through the series:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=30 bc250 'bash ~/bc5-work/exp0385/kstream0385.sh' > raw/kernel-stream.txt
   ```
5. **Each run,** in the background; the `RESULT` line gives the mean patch and so the next step:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=30 bc250 'timeout -k 10 540 ~/bc5-work/exp0385/run0385.sh K4 52ee672646ca6087 78f25172'
   ```
6. **Summaries after each run:**
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'cat ~/bc5-work/exp0385/K4.raw.tar' > raw/K4.raw.tar
   ```
   Then unpack into `raw/` and delete the tar.
7. **Release:**
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'cd ~/bc5-work || exit 1; pgrep -a "^kyty_emulator" && { echo "an emulator runs: not released"; exit 1; }; S=$(cd _SaveData && find PPSA03671 -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); sed -i "/^water session exp 0385/d" BOX-LOCK; echo "water exp 0385 | released: live saves $S (C locale); snapshots and shots deleted unviewed, the journals private | $(date "+%F %T")" >> BOX-QUEUE; ls ~/bc5-data/priv/exp0385/ exp0385/r-*/shots 2>&1 | head; echo "--- BOX-LOCK:"; cat BOX-LOCK; tail -1 BOX-QUEUE'
   ```
8. Check the stream has ended, then report the result and "box free" to the top session. `play-pkg-0385.diff` and
   `input-0385.cfg` come in each run's tar.

**Result.** Pending.

**Verdict.** Pending.
