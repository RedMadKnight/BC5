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

## The test build

The maintainer, 2026-10-31: every candidate fix and catcher goes into one test build at once, each with an on/off switch, and only
then does testing start. So this is not a plain repeat any more. The series runs a private binary: the shared objects of 78f25172
with a private backend archive (`backend/`, `bc5/lake_probe.hpp`). With `BC5_DIRECT_LAKE_CTL` unset none of it runs. Shared builds,
patch 0001 and the launcher do not change.

The host re-reads a control file every 32 GFX jobs, so **one run with holes can turn each switch on and off**. That sets each arm
against all-off shots of the same run, which the run-to-run variation (0.8–32 %) would otherwise hide.

| Shots | Switches (`arms0385.txt`) | What it tests |
|---|---|---|
| 0–16 | all off | The poller's window: F486's test, unchanged, and whether the run qualifies |
| 17–20 | `census=1 zpass=1` | **Catchers.** Per job: lake writers, those inside a COND_EXEC, nested IBs, predication. Per writer: passed samples, and whether the CP skipped it |
| 21–23 | `cache=wbinv cache_at=each` | Stale GL2 data (GL2 write-back and invalidate before each lake writer) |
| 24–26 | `cull=1` | A barrier after each culling pass (F355's four programs) |
| 27–29 | `pfp=1` | `PFP_SYNC_ME` before each COND_EXEC and indirect lake writer |
| 30–32 | `dbmeta=1` | `FLUSH_AND_INV_DB_META` after each HTILE fill (F310) |
| 33–35 | `idle=1` | CS and PS partial flushes before the first writer |
| 36–38 | `nohiz=1` | HiZ and HiS forced off for the writers (what F486 left open) |
| 39–41 | `trackercf=1` | The host's state tracker stops at a CHAIN (F761) |
| 42–44 | `cache=all cache_at=each` | The kernel's whole cache set before each writer |
| 45–47 | all of them | In case only a combination works |
| 48–52 | all off | Back to the start: an arm that seemed to clear should not hold here |

These are hypotheses; none is proven. The fixes come one at a time so that a hang names its arm, and all together last.

**Off and on, per switch.** With `BC5_DIRECT_LAKE_CTL` unset the module does not exist at run time: no tracker, no BO, no insert. With it set and
a switch off, that switch inserts nothing (unit tests). Each change of the switches first logs a `period` line of what the ending span did, and an arm
counts only if its own count moved; otherwise it reads NOT EFFECTIVE, whatever its shots show.

| Switch | Off | On, what the GPU gets | Its evidence in `<tag>.switches.txt` |
|---|---|---|---|
| `cache=` | Title's own barriers only | `ACQUIRE_MEM` with the chosen GCR bits before the writer | `inserted_words` |
| `cull=1` | No insert | `CS_PARTIAL_FLUSH` and GL2 write-back and invalidate after each of F355's programs | `cull_barriers` |
| `pfp=1` | No insert | `PFP_SYNC_ME` before COND_EXEC and indirect writers | `inserted_words` |
| `dbmeta=1` | No insert | `CS_PARTIAL_FLUSH`, GL2 write-back and invalidate, `FLUSH_AND_INV_DB_META` after each HTILE fill | `htile_fills` |
| `idle=1` | No insert | CS and PS partial flushes before the first writer | `inserted_words` |
| `nohiz=1` | No insert | `DB_RENDER_OVERRIDE` with HiZ and HiS forced off for the writers, the title's value restored after | `inserted_words` |
| `trackercf=1` | The tracker walks past a CHAIN, as every shared build | It stops there | `chain_stops` |
| `census=1` | No line | One line per job, 2,000 at most; no packet | the census lines |
| `zpass=1` | No insert | `DB_COUNT_CONTROL` set for the writers and restored, `ZPASS_DONE` around each | `inserted_words`, `<tag>.zp.txt` |

**Limits.**

| What | Bound |
|---|---|
| Census | 2,000 lines, ~300 KB of the private log |
| Catcher | A 16-MiB GTT BO, 65,536 records, about 500 frames at ~130 writers each; the `.dat` file at most 16 MiB and its `.meta` about 3 MiB, both private and deleted with the snapshots |
| Snapshots | ~2.7 GB a run, deleted after a pass; kept after a failure, so ~8 GB at the worst |
| Disk | No claim or run at 80 %; a run stops at 90 % (`disk_pct`, checked every 3 s) |
| Private tree | `exp0385/tb`; its size is printed by build and has not been measured |
| Journal | `BC5_DIRECT_JOURNAL=min`, as K1–K3, for at most 560 s; its size goes into `<tag>.journal.txt` |
| Time | Build 7 min, each emulator 560 s, each run 13 min, the series 45 min |

**Audio and guards.** The test build changes no audio. Patch 0001 is byte for byte fab8660's and carries exp 0372's pad audio route (5 marks), and the private binary
links the shared objects unchanged, so exp 0372's replug check is not due: this is not an audio change. The functional guards stay required by the manifest, and
`BC5_DIRECT_REBASE_DISPATCH` stays removed and forbidden (F765). `test0385.py` checks all of this.

**Backup.** Nothing shared is replaced, so there is nothing to back up: the private binary, its build and all evidence stay in `exp0385/` and `priv/exp0385/`.

**Arm rule, fixed before the runs.** With the all-off shots at a median of 20 % or more, an arm **clears the holes** if every one of its
shots is at 12 % or less (`gates0385.py arms`; K2, K3 and H1 sat at 9.2–9.9 %). A clearing arm is a lead, not a fix: three shots can
coincide with a clean phase, so it gets its own repeat before anything moves toward a shared build. With no holes in the all-off shots
a run says nothing about the arms. `trackercf` acts where the host's prefixes do, so a null there is weak unless the census shows CHAINs.

**The catcher's reading.** A writer whose passed samples fall in some frames is the one losing the lake's cells. A record whose begin stayed
unwritten was skipped by the CP. Lake writers in nested IBs cannot be wrapped; the census counts them.

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
| Live saves | no fixed pin, because the maintainer's play moves it: read under the claim's lock, printed by the claim, and held for the series in `live.sum` (C locale) | this run. Compared only, never restored |
| `saves-lake-1153` | no earlier value exists: its sum is recorded under the lock at claim, then checked before and after each run | this run |
| `exp0330/wd`'s links | the listing's sha256 is recorded at setup; every link must point into `~/bc5-work` | the layout of D19's smokes |
| Our kit | `kit.sha256`, checked on the box by setup | this commit |
| `testbuild.tar` | `tb.sha256`, made from this commit's `backend` tree at the slot, checked by build | this commit |
| Private binary | its md5 is recorded after the build and checked before each run and against the running emulator | this run |
| Source | fab8660, main. This branch carries no build change | the top session |

The lean build is not used, because the RT proof reads the journal. `input-0385.cfg` is exp 0369's `input-0369.cfg` byte for
byte, and `patch0385.py` is exp 0197's tool with one comment line added, so neither depends on an older experiment's directory
staying as it was. Changes since K1–K3's build 1000ad2a that this repo records include the NP and libc fixes (F740, F741),
`BC5_DIRECT_REBASE_DISPATCH` removed (F765), lean's list (F766) and `=0` meaning off for seven switches (F767).

## Plan

**Runs.** At most three, tags **K4, K5, K6**, in that order, one GPU workload. `box0385.sh` enforces the order and the limit. The
series ends at the first run with a mean patch of 20 % or more over the all-off shots 0–16. A failed route uses its attempt and is not a pass.

**Build first.** `build` makes the private backend, runs its Catch2 tests, and only if they pass links the shared normal build's objects
with that archive. CPU only, at nice 19, no emulator, ~5 min (exp 0381's was). A failed build ends with nothing linked.

**Length.**

| Step | Expected |
|---|---|
| Claim, copy the kit, setup, self-test | ~1 min |
| Private build and its tests | ~5 min |
| One run: the view at ~200 s, then 53 shots 5 s apart, analysis and clean-up ~0:35 | ~8.5 min |
| Release | ~0:30 |
| **Total** | **~15 min if K4 has holes, ~32 min for all three** |
| **Series deadline** | **45 min from the claim, recovery and release included** |

**The deadline is enforced, not described.** It is written at the claim and read by every step. No run starts with under 15 min
left (13 for the run, 2 for recovery), and that attempt is then not used. Each emulator lives at most 560 s. A watchdog, started by
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

**Risk added by the test build.** The arms change what the GPU runs while the title plays. A fix can hang the ring or take the machine
down. The kernel gate stops the series at the first line, and the arm in force is in `arms.log`.

**Written on the box:** `~/bc5-work/exp0385/` with the private build in `tb/`, `~/bc5-data/priv/exp0385/`, the private journal under `~/bc5-data/captures/play-*`, the
launcher's `route-record.txt`, and our BOX-LOCK and BOX-QUEUE lines. No shot or snapshot is viewed.

## Commands, in order, after the top session's slot

Each is one plain command, from this directory, in the forms the maintainer's allow rules cover. Owner: this session. `<token>` comes
from step 1.

1. **Claim,** the first thing that touches the box. It prints `TOKEN=`:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'bash -s -- claim' < box0385.sh
   ```
2. **Kit,** after making `testbuild.tar` on the laptop from this commit's `backend` tree, without patch 0001:
   ```
   git archive -o testbuild.tar HEAD:backend ':!kytyplus-patches'
   ```
   ```
   sha256sum testbuild.tar > tb.sha256
   ```
   ```
   scp -o ConnectTimeout=10 -o BatchMode=yes box0385.sh gates0385.py pl0385.py sn0385.py tz0385.py bt0362.sh patch0385.py swz0248-z4.json input-0385.cfg arms0385.txt relink0385.py zp0385.py kit.sha256 testbuild.tar tb.sha256 bc250:bc5-work/exp0385/
   ```
3. **Setup and build:**
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes bc250 'bash ~/bc5-work/exp0385/box0385.sh setup <token>'
   ```
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=30 bc250 'timeout -k 30 480 bash ~/bc5-work/exp0385/box0385.sh build <token>'
   ```
4. **Kernel stream,** in the background through the series:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=30 bc250 'bash ~/bc5-work/exp0385/box0385.sh kstream <token>' > raw/kernel-stream.txt
   ```
5. **Each run,** in the background. Exit 0 pass, 10 route failure, 1 stop; the `RESULT` line gives the mean patch and the next step:
   ```
   ssh -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=30 bc250 'timeout -k 90 840 bash ~/bc5-work/exp0385/box0385.sh run <token> K4'
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
| The build fails | Nothing linked, the shared builds untouched, state stays `setup` | `release`; the log is in `tb/raw/` |
| The laptop is gone | The watchdog stops ours at 43 min and releases at 45 | The top session sees the BOX-QUEUE line |
| Another line in the lock | No launch, ours stopped, that line kept | `release` takes out only ours |
| `bc5-mount` does not leave | Never killed; release refuses and the lock stays | Ask the top session |
| Our lock line is gone | Nothing is touched; release refuses | Ask the top session |

Rollback of this preparation: discard branches `exp/0385-r3` and `exp/0385-testbuild`. `exp/0385-r2` stays at 65ac8485, `exp/0385-lake-holes-repeat`
at a49c2c7, and a9aeed5 at local tag `exp0385-a9aeed5`. Rollback on the box: nothing shared changes, so `release` is enough.

## Changes from a49c2c7 (REVIEW-PORTS-27)

- `box0385.sh` replaces `run0385.sh`, `ab0385.sh`, `setup0385.sh`, `ana0385.sh` and `kstream0385.sh`. `bench0385.sh`'s route is its `bench`
  subcommand, its keys and timing unchanged, and it no longer looks up or stops a process.
- `gates0385.py` is new: the manifest, the fail-closed run gates and the decision rule above.
- `pl0385.py` is given the run's emulator by pid and start time and the exact lock line, and now exits with a status.
- `mkkit0385.py` is gone. The kit is pinned by `kit.sha256`.
- The question, the thresholds and the K4–K6 limit are unchanged.

**r3, the test build, on the maintainer's word:** `backend/` gains `lake_probe` and a CHAIN switch in `full_state`; `direct.cpp` allocates the
records' BO and calls the module, all behind `BC5_DIRECT_LAKE_CTL`. `box0385.sh` gains `build`, runs the private binary and writes the arms;
`relink0385.py`, `zp0385.py` and `arms0385.txt` are new. The bench takes 53 shots instead of 20, and the series deadline is 45 min instead of 30.

## Tests

`python test0385.py <work dir>` runs the real `box0385.sh` and `gates0385.py` on the laptop, with no box, no launcher and no game, and
with HOME and PATH unchanged. Roots and stand-ins are accepted only from a `0385-test-` path. Stand-ins sit at the box's edge alone:
clock, dmesg, container, shots and the poller. Real processes stand in for the emulator (a copy of `sleep.exe` named `kyty_emulator`),
so the identity and signal code reads a real `/proc`, with a foreign sentinel running beside it.

**Run on these files:** 101 of 102 in one full pass, 49 min (`raw/test0385.txt`). The one failure was the test's own setting: with a time limit of 1 s the watchdog
stopped the stand-in emulator before the run had saved its environment, and the run stopped, as it should. With a limit of 30 s that case passes
(`raw/test0385-rerun.txt`). The module's own tests, 16 of 16 under the backend's warning flags and ASan, and a compile of the real `direct.cpp` lines between
stand-ins for libdrm, are in `raw/lake-module.txt` (`testbuild/run_laptop.py`, `testbuild/check_wiring.py`). `direct.cpp` as a whole has not been compiled: the box's
private build is the first to do it.

**What the cases cover:** the claim against a foreign line before it, a new file and a held-open writer during it, and six real
claimants at once; a link at the lock, the queue, the save copy, the tree, its parent and its root, junctions included; ownership
lost mid-run; a foreign sentinel and another series' process beside TERM, KILL, a reused pid and a release; a dropped reader; the
deadline's stop and release; the exact release with foreign lines; every stop and route failure above, each checked for kept evidence;
and the whole order from claim to release.

**What they found in the code, all fixed:** a `local` line that expanded a variable before it was set; two races in which the watchdog
stopped a healthy run, one at its start and one at its end; a third, in which the watchdog's stop at the time limit read as a crash; and
a still image that stopped the series instead of counting as a failed route.

**Not reachable on this laptop:** the real distrobox and podman chain, `setsid`, `/proc/PID/mem` (the poller's reads; its lock test is
checked on its own), a foreign uid, a second file system, `mkdir -m 700` and the kernel's access times. Those first run on the box. So do all the test build's GPU packets:
the unit tests prove what goes into the buffer, not what the GPU does with it. The RB count of gfx1013 and `FORCE_HIZ`/`FORCE_HIS` on hardware stay TODO(verify).

**Result.** Pending.

**Verdict.** Pending.
