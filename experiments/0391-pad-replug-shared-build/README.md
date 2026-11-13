# 0391 — Exp 0372's software replug check on the shared normal build

**Status: open.** The laptop part is done: the scripts, their generator and a laptop test with stand-ins. Nothing has run
on the box. The box run waits for a slot the top session names (after exp 0389, the 0388 read, the mount re-read and exp
0390); the maintainer gave his consent on 2026-11-01 ("zgoda", twice). The Verdict stays empty until then. The experiment
number is provisional: it was taken from the repository side only (0390 is the highest branch, 0383 the highest
directory); the box half of the claim (`~/bc5-work/exp0391`) is made by the run's own claim in the slot.

**Question.** Does the shared normal build of 2026-10-31 (78f25172, patch 0001 with exp 0372's pad audio route) still pass
exp 0372's software replug test: after each pull of the DualSense's PipeWire card profile the pad-routed port closes its
stream and reopens it on the DualSense sink, no pad stream is ever linked to another sink, nothing is written to the pad
while the controller is away, and the main mix keeps its pacing? Exp 0372 showed this on its private build (P1, P2) on
2026-10-29; since then patch 0001 was regenerated and rebuilt twice (F330's rumble worker and the pad-speaker switch, the
0380 series), and the standing audio rule says every audio change gets this check before the maintainer's physical replug
and a DualShock 4 check.

## Setup

Laptop only, 2026-11-01 06:1x–06:3x: no box access, no GPU run. One guarded read before the design (06:1x, under exp
0389's lock line, nothing written) gave the lock state, the shared binary's md5 and the absence of exp 0372's scripts on
the box; the top session then asked for no further reads without its GO.

The scripts (in this directory; `mk0391.py` makes four of them from reviewed sources with counted replacements, LESSONS
R05/R10; `raw/laptop-md5.txt` has every md5):

| file | from | what differs (marked `0391:` in the file) |
|---|---|---|
| `s6n0391.sh` | `coordination/d19/s6n-d19.sh` (sha256 d7cf6e33, the D19 smoke runner: the S6N route, the shared build, the token) | RT on, 420 s; `run0391.sh` owns the lock: the exact line (`E0391_LOCKLINE`) is checked at the start, before the launch and at every poll, never written; no live-save sum as a gate (the live saves are snapshot by name and compared at the end only); `KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_TRACE=1` in the emulator's environment, proved there; no stall-sampler requests or gate, no menu shots; the audio and rumble lines go to `raw/<tag>-audio-lines.txt` |
| `replug0391.sh` | exp 0372's `raw/replug0372.sh` | the run is recognised by its exact lock line and the emulator by the `D19_OWNER` token in its environment; private paths under `~/bc5-work/exp0391/run` |
| `streams0391.py` | exp 0372's `raw/streams0372.py` | unchanged |
| `run0391.sh` | exp 0390's `run0390.sh` (dba7e514; the d19 claim by hard link, the token, the capped run, the kernel stream, the release by token) | the second argument is the replug mode (`pulls` or `late`), not a fix switch; the pins are the shared binary's first 8 hex (`NORMAL8=78f25172`, the full md5 recorded in `-pins.txt`), the launcher and `bc5-run.env`; the replug script starts beside the S6N run with the same token; `check0391.py` classifies; 420 s of play, the runner capped at 600 s, a claim needs 840 s to the deadline; the lock line starts with `anyps5-ports exp0391 \| token …` |
| `go0391.sh` | exp 0390's `go0390.sh` | the mode; a 16-minute deadline by default; after the run the text results come to `raw/` (never `-environ.bin`, never the play log) |
| `check0391.py` | new | the classifier, fails closed: PASS, FAIL, NO_TEST (the run passed but no pull happened: no DualSense card), INVALID (a file missing) |
| `pins0391.env` | new | `NORMAL8` as the top session named the shared binary; `LAUNCHER` and `RUN_ENV` from exp 0390's pins (the same `play-pkg.sh` 55531ab6 that exp 0372 and D19 read) |
| `test0391.sh` | new | the laptop test, below |

What PASS needs, each from the run's own files (`check0391.py`'s docstring): the S6N verdict `pass`; the replug sequence
to `sequence done` with 3 pulls (`late`: 1); in every `pw-dump` read every pad stream linked to a DualSense sink or to
nothing; after every pull a `closed (…)` and then an `opened on DualSense … after an output device was added` line in the
replug file's log tails (no clock mapping needed); no `(pad) … device playing` trace line while the profile was off (the
trace's t is placed on the box clock from the first `closed` line, which follows the profile change within ~50 ms; the
window is shrunk by 1.5 s at each end); no `rumble: pad instance …` failure line. Reported, not gated: the main port's
smallest `held` and SDL queue in the 3 s after each reopen, the rumble write count.

Not in the gate on purpose: `input.cfg` and the learned file (recorded; `s6n0391.sh` copies both privately and forces
RT on), the route saves' sum (the directory's presence only; exp 0196's copy is read, never written).

### The slot (from the laptop, after the top session's signal)

```
cd experiments/0391-pad-replug-shared-build && bash go0391.sh A1 pulls
```

Claim (the hard link; refused at once under a foreign line, an emulator, a build, the compression job, a full disk or
under 840 s to the deadline), send and compare the six files, start the detached run under its own `timeout`, stream the
kernel log to `raw/A1-kernel-stream.txt`, poll `A1-done.txt`, fetch the text results. About 10 minutes from the claim to
the release; the deadline given is 16 minutes. A second run (`A2 late`) only if the top session's slot allows it.
Recovery if the laptop loses the box: `ssh bc250 'bash -s -- release <token>' < run0391.sh` (stops the token's
processes, frees the lock only if it holds our exact line).

A DualShock 4 or no pad gives NO_TEST (no DualSense card in PipeWire): the maintainer's DualSense must be on USB. The
maintainer's physical replug and the DualShock 4 check are separate steps, his.

### The laptop test (`bash test0391.sh`, `raw/test0391-laptop.txt`, 29 of 29)

- `check0391.py` on exp 0372's real P1 and P2 files: PASS with 3 and 1 pulls, the same facts as exp 0372's README (one
  `closed` and one `opened … after` per pull, the main port's queue minimum 0 ms in the 3 s after each reopen, no pad stream
  on another sink); on P1 with a pad stream rewritten onto the dock: FAIL; on a run without a DualSense: NO_TEST; on a
  crashed run without pulls: FAIL, not NO_TEST; a missing file: INVALID; two pulls of three: FAIL.
- The real `run0391.sh` on a stand-in tree under a `d19-test-` path (its own `D19_FAKE` hook replaces the box's reads:
  pgrep, /proc, setsid, df, systemctl; stand-in `s6n0391.sh` and `replug0391.sh` play back P1's files): a foreign lock
  line, an emulator, a 100-s deadline, a bad mode, a second claim and a used tag are refused and the lock is left as it was;
  the claim writes our exact line with the token to BOX-LOCK, the queue and the token file; start → run → `RESULT T1 runner
  0 check 0 CLASS PASS mode pulls pulls 3`, the lock empty afterwards, the done line in the queue; the S6N stand-in got the
  token, the shared binary, its md5, the launcher md5 and 420 s; the replug stand-in got the mode, the token and the lock
  line; a release under a foreign line is refused and the line kept; a changed launcher stops the run before the launch and
  still releases.
- Not covered on the laptop: `go0391.sh` itself (ssh/scp), the derived launcher's anchors against today's `play-pkg.sh`
  (the same md5 as exp 0390's pin, so the anchors held on 2026-11-01), PipeWire on the box, the real emulator.

**Result.** (empty: no box run yet)

**Verdict.** None written (noted 2026-11-13). The run this experiment planned was never made under its own name. Its harness was used later, by exp 0413 and by exp 0416 and exp 0417, on the builds of 2026-11-12 and 2026-11-13: software replug runs R5, R7, R8 (on the shared normal build fe0933c0) and R9, each CLASS PASS with three pulls, raw files under `experiments/0413-np-session-v2-shared/integration/replug/raw/`; see `docs/HANDOFF.md` F828.
