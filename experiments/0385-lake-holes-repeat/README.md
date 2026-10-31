# 0385 — The night lake's holes on the merged build: does F486's coverage hold on a run with holes

**Status: plan only.** Written on the laptop on 2026-10-31, before any box access. Nothing below has run. This revision answers
Codex's REVIEW-PORTS-27 (HOLD on a49c2c7). Findings, if any, take numbers from F720 (range F720–F739, given by the top session).

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

## Build and inputs (from the top session, REVIEW-PORTS-27 and the repo; this session has not read the box)

All are checked under the lock before anything of ours is copied, and again before each run. A mismatch stops with nothing
launched.

| Input | Pin | Source of the pin |
|---|---|---|
| Shared normal binary | md5 78f251729b06001d67d642ff06773758 | D19; REVIEW-PORTS-27 |
| Backend archive | md5 3292bdaf0aca16ca9922a7f732386aa8 | D19 |
| `play-pkg.sh` | md5 55531ab6277d6816c0603a7a6c6d62b4 | the top session: unchanged by D19 |
| `bc5-run.env` | md5 cb8ad5fcfd6eac2a5cafac2a501b3eba | the top session: unchanged by D19 |
| Live saves | 52ee672646ca6087, C locale | the top session. Compared only, never restored |
| `saves-lake-1153` | no earlier value exists: its sum is recorded under the lock at claim, then checked before and after each run | this run |
| `exp0330/wd`'s links | the listing's sha256 is recorded at setup; every link must point into `~/bc5-work` | the layout of D19's smokes |
| Our kit | `kit.sha256`, checked on the box by setup | this commit |
| Source | fab8660, main. This branch carries no build change | the top session |

The lean build is not used, because the RT proof reads the journal. `input-0385.cfg` is exp 0369's `input-0369.cfg` byte for
byte, and `patch0385.py` is exp 0197's tool with one comment line added, so neither depends on an older experiment's directory
staying as it was. Changes since K1–K3's build 1000ad2a that this repo records include the NP and libc fixes (F740, F741),
`BC5_DIRECT_REBASE_DISPATCH` removed (F765), lean's list (F766) and `=0` meaning off for seven switches (F767).

## Plan

**Runs.** At most three, tags **K4, K5, K6**, in that order, one GPU workload. `box0385.sh` enforces the order and the limit. The
series ends at the first run with a mean shot patch of 20 % or more. A failed route uses its attempt and is not a pass.

**Length.**

| Step | Expected |
|---|---|
| Claim, copy the kit, setup, self-test | ~1 min |
| One run: bench ~5:05–5:16 (K2, K3), analysis and clean-up ~0:35 | ~6 min |
| Release | ~0:30 |
| **Total** | **~7.5 min if K4 has holes, ~20 min for all three** |
| **Series deadline** | **30 min from the claim, recovery and release included** |

**The deadline is enforced, not described.** It is written at the claim and read by every step. No run starts with under 12 min
left (10 for the run, 2 for recovery), and that attempt is then not used. Each emulator lives at most 390 s. A watchdog, started by
setup in its own session, stops what is ours at 2 min before the deadline and releases at the deadline. `status`, `stop` and
`release` still work after it. The kernel stream ends with our lock line or the deadline.

**RT and the lake's reflections.** RT on in every run, nothing skipped. Unlike the lake runs of exps 0194–0295, the launcher comes
from today's `play-pkg.sh`, with `BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-0}` (exp 0382's README, read for 55531ab6), so the
traversal (0x11d049aa00, 0x11d04a6000, 0x11d04bb900) and the BVH compaction (0x909974400) run. This is now gated, not printed:
- **Effective options:** right after the start, `gates0385.py manifest` reads this emulator's own exec environment against an allow
  list (D19's table for this launcher and settings file, with this experiment's paths). A missing guard, a changed value, a forbidden
  name (`KYTY_BC5_RT` at any value, the skip and experiment switches) or an unknown option stops the series before the bench.
- **Journal:** the directory comes from that emulator's `BC5_GC_DUMP_DIR`, not from "the newest one". It must be readable and fresh.
  Any `ray tracing off:`, `skip pgm` or `TIMEOUT` line stops the series, and a count that could not be read is a stop, never a zero.
- **Privacy:** the raw environment stays in `~/bc5-data/priv/exp0385/evidence`, mode 600. Git gets table names and values only.

**Save copy.** `~/bc5-work/saves-lake-1153`, as in K1–K3, copied into a new working directory of our own, `~/bc5-work/exp0385/wd`.
`exp0299/wd` is no longer used or touched. The save copy is the only thing deleted before a run, by `own_rm` below. The live saves
are compared only, in the C locale, and never restored over. The launcher's logs, working directory, save directory and learned file
are private too (`play-pkg-0385.diff`, 6 lines changed, 1 added, derived here from the pinned `play-pkg.sh`, not from an older
derivative). It keeps the launcher's `route-record.txt` and its capture directory, as every run does.

**Ownership.** One lock line with one token for the whole series, no per-run line.
- The claim is the reviewed D19 form: the empty lock goes aside and `ln` publishes our line, which fails if anyone recreated it; a
  writer that had the old file open shows up in the aside copy. It refuses a link, a foreign line and a leftover claim.
- The lock is checked before every mutation and before the launch. Any other content means ownership is lost: no launch, no mutation,
  ours are stopped, the foreign line stays.
- Release takes out only our exact line, keeps every other line in order, and fails closed if our line is gone.
- Distrobox starts the launcher through podman, so it and the emulator are in no process group of ours. A process is ours only if its
  exec environment holds our token, passed by `env` inside the container. Host children (bench, poller, shots) carry a second mark.
  The host side of the launch chain carries none, so a conmon or pause process started on our behalf can never be taken for ours.
- Every signal re-checks the mark first. A process without it is never signalled. `bc5-mount` is never killed (exp 0288): if it does
  not leave, the lock stays and the top session is told.

**Stops.** Any of these stops the series with the evidence kept and the lock held for release: a kernel fault, ring timeout, reset or
devcoredump (no analysis); an unreadable kernel log; live saves, lake save or shared learned file changed; a lost lock; an emulator
that is not ours; a failed identity (binary, working directory, environment); a failed manifest; a journal, RT or skip failure; a failed
poller, patch tool or analysis; a failed archive; a dead emulator; `/var/home` at 80 %; a signal. A classifier refusal of any box step
is reported to the top session and not worked around.

**Route failure.** The bench failing, the lake save not read, the emulator's time running out, or too little evidence of the lake
(under 500 frames, 100 snapshots, 1,000 flips or 30 finals; K2 and K3 had 2,228 and 2,069 frames, 408 and 372 snapshots, 37 and 182
finals). Exit 10: the attempt is used, the evidence stays, and the next tag may run.

**Deletion.** Only after every gate passed and the summaries' archive was written and listed in full: the run's snapshots
(`~/bc5-data/priv/exp0385/<tag>`, ~2.7 GB) and shots, unviewed, by `own_rm`. It accepts only these and the save copy, each a plain
directory of ours at its canonical place, holding no link and no foreign file. Nothing else is deleted, and nothing at all after a
failure.

**Written on the box:** `~/bc5-work/exp0385/`, `~/bc5-data/priv/exp0385/`, the private journal under `~/bc5-data/captures/play-*`, the
launcher's `route-record.txt`, and our BOX-LOCK and BOX-QUEUE lines. No shot or snapshot is viewed.

## Commands, in order, after the top session's slot

Each is one plain command, from this directory, in the forms the maintainer's allow rules cover. Owner: this session. `<token>` comes
from step 1.

1. **Claim,** the first thing that touches the box. It prints `TOKEN=`:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'bash -s -- claim' < box0385.sh
   ```
2. **Kit:**
   ```
   scp -o ConnectTimeout=10 -o BatchMode=yes box0385.sh gates0385.py pl0385.py sn0385.py tz0385.py bt0362.sh patch0385.py swz0248-z4.json input-0385.cfg kit.sha256 bc250:bc5-work/exp0385/
   ```
3. **Setup:**
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'bash ~/bc5-work/exp0385/box0385.sh setup <token>'
   ```
4. **Kernel stream,** in the background through the series:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=30 bc250 'bash ~/bc5-work/exp0385/box0385.sh kstream <token>' > raw/kernel-stream.txt
   ```
5. **Each run,** in the background. Exit 0 pass, 10 route failure, 1 stop; the `RESULT` line gives the mean patch and the next step:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=30 bc250 'timeout -k 90 660 bash ~/bc5-work/exp0385/box0385.sh run <token> K4'
   ```
6. **Summaries after a passed run;** compare with the `RESULT` line's sha256, unpack into `raw/`, delete the tar:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'cat ~/bc5-work/exp0385/K4.raw.tar' > raw/K4.raw.tar
   ```
7. **Release,** then check that the stream has ended and report the result and "box free" to the top session:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'bash ~/bc5-work/exp0385/box0385.sh release <token>'
   ```

**Recovery.**

| What happened | What holds | What to do |
|---|---|---|
| The ssh of a run dropped | The run goes on and logs to `<tag>.run.log` | `status <token>`, then `tail` that log |
| The claim's answer was lost | Lock line and `exp0385/token` agree on the box | Read both; carry on only if the lock line holds that token |
| A run exits 1 | Series stopped, ours stopped, evidence kept, lock held | `status`, `release`, report; the top session decides on the evidence |
| The run process was killed | The watchdog stops ours within seconds | `status`, `release` |
| The laptop is gone | The watchdog stops ours at 28 min and releases at 30 | The top session sees the BOX-QUEUE line |
| Another line in the lock | No launch, ours stopped, that line kept | `release` takes out only ours |
| `bc5-mount` does not leave | Never killed; release refuses and the lock stays | Ask the top session |
| Our lock line is gone | Nothing is touched; release refuses | Ask the top session |

Rollback of this preparation: discard branch `exp/0385-r2`. `exp/0385-lake-holes-repeat` stays at a49c2c7, and a9aeed5 stays at local tag
`exp0385-a9aeed5`.

## Changes from a49c2c7 (REVIEW-PORTS-27)

- `box0385.sh` replaces `run0385.sh`, `ab0385.sh`, `setup0385.sh`, `ana0385.sh` and `kstream0385.sh`. `bench0385.sh`'s route is its `bench`
  subcommand, its keys and timing unchanged, and it no longer looks up or stops a process.
- `gates0385.py` is new: the manifest, the fail-closed run gates and the decision rule above.
- `pl0385.py` is given the run's emulator by pid and start time and the exact lock line, and now exits with a status.
- `mkkit0385.py` is gone. The kit is pinned by `kit.sha256`.
- The question, the thresholds and the K4–K6 limit are unchanged.

## Tests

`python test0385.py <work dir>` runs the real `box0385.sh` and `gates0385.py` on the laptop, with no box, no launcher and no game, and
with HOME and PATH unchanged. Roots and stand-ins are accepted only from a `0385-test-` path. Stand-ins sit at the box's edge alone:
clock, dmesg, container, shots and the poller. Real processes stand in for the emulator (a copy of `sleep.exe` named `kyty_emulator`),
so the identity and signal code reads a real `/proc`, with a foreign sentinel running beside it.

**Run on these files:** 83 of 84 in one full pass, 40 min (`raw/test0385.txt`). The one failure was the test's own fixture, which
lacked the poller file that a gate had just begun to read; with that file added, that case passes (`raw/test0385-rerun.txt`).

**What the cases cover:** the claim against a foreign line before it, a new file and a held-open writer during it, and six real
claimants at once; a link at the lock, the queue, the save copy, the tree, its parent and its root, junctions included; ownership
lost mid-run; a foreign sentinel and another series' process beside TERM, KILL, a reused pid and a release; a dropped reader; the
deadline's stop and release; the exact release with foreign lines; every stop and route failure above, each checked for kept evidence;
and the whole order from claim to release.

**What they found in the code, all fixed:** a `local` line that expanded a variable before it was set; two races in which the watchdog
stopped a healthy run, one at its start and one at its end; a third, in which the watchdog's stop at the time limit read as a crash; and
a still image that stopped the series instead of counting as a failed route.

**Not reachable on this laptop:** the real distrobox and podman chain, `setsid`, `/proc/PID/mem` (the poller's reads; its lock test is
checked on its own), a foreign uid, a second file system, `mkdir -m 700` and the kernel's access times. Those first run on the box.

**Result.** Pending.

**Verdict.** Pending.
