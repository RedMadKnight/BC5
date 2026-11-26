# The night series on the test build T: arms (proposal of 2026-11-14, to be agreed with the guardian; nothing run)

Asked by the top session. T is `test-build.md` (patch fec3d656, not built yet). The series is the long walk of the
second title to G+620, RT on, a private copy of the save, no pad key, as the walks of README sections 14 and 15 and
exp 0412's sections 91 to 93.

## Is `KYTY_BC5_APR_POSIX=direct` in B, and can T run without it?

- [M] It is a row of `kFixes` in the shared build B (patch 27b6416f) as well as in F, G and T; it came with the
  integration of 2026-11-13 01:50 (patch 4651d1d3). So it is not a difference between B and F.
- [M] In B the row is applied without overwrite: `KYTY_BC5_APR_POSIX=0` in the environment turns it off. Since
  candidate E (and so in F, G, T) the rows of `kFixes` and `kDefaults` are forced with overwrite: the word in the
  environment is overwritten, and no arm without it could be run.
- Added to T for this (`mkdiag0419.py`, CPU test `test0419diag.cpp`, all ok): the diagnostic
  `KYTY_BC5_DIAG_UNFORCE=<NAME>[,<NAME>...]`. A listed row of `kFixes` or `kDefaults` is not applied, the
  environment's own value stands, and a line on stderr says so. Unset: everything forced as before. It is a test
  build's diagnostic and must not enter a launcher or shortcut.

## The arms

Every arm: `KYTY_BC5_AUDIO_TRAIL=1` and the guardian's log-only set of today's chains (`KYTY_BC5_MEM_FIRSTFAIL=1
KYTY_BC5_TRAP_LOG=1 BC5_GUARD_COVER_LOG=1 BC5_TIMEOUT_LAYOUT=1 BC5_DISPATCH_COUNT=1 BC5_FAULT_POINTERS=1` and its
snapshot word). They only log; the trail costs one small record per AJM call.

| Arm | Words on top of that | What it is for |
|---|---|---|
| tA | none | T's defaults: the fault's rate on T, and the first fault with the trail names the source's class, its base and stream pointers and the codec's buffers (`audio-record-fault.md` section 8) |
| tJ | `KYTY_BC5_AJM_DEFER=1 KYTY_BC5_AJM_LIVE_IDS=1` | both AJM fix candidates together |
| tP | `KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0` | APR reads the old way (open, fread, staging copy): the one candidate of ours on the stream side |
| tD | `BC5_GUARD_DESC_TARGETS=2` | the guardian's arm (agreed 2026-11-14): dt412, log only. It walks every submitted buffer on the submitting thread and has never run in the host, so it is an arm of its own, measured against tA; it gives the MiB that mode 1 would import |

Order: tA tJ tP tD, repeated, so that a drift of the box cannot pose as an effect. One build, one lock line for the
chain, a stop file checked between arms and tested dry before the first walk.

## Stop rule (LESSONS R55)

The chain stops before the next arm after any kernel GPU line, a new fault record, or an unknown end, also when the
reset succeeded. **One named exception, written here by the top session's order:** the title's CPU fault at
eboot+0x1b349f (exit 65, an access violation whose crash text names that address, 0 kernel lines, no new fault
record) does not stop the chain: it is the event the series is looking for. Any other guest fault stops it.

## Size, and what the series can and cannot show

- Fixed before the start: 60 walks (15 per arm) or 3 GPU hangs, whichever comes first; the same 60 walks are the
  count of `f403-f813-series.md`, with the arms kept apart in the table.
- The CPU fault has come 2 times in 28 long walks of the F family (12 of this experiment, 16 of the guardian's on
  b413a916 by its parts note). At that rate 15 walks of one arm show it once on average, and 0 of 15
  against 1 or 2 of 15 separates nothing. **The arms give a direction, not a verdict.**
- What does decide something: (a) one fault in any arm with the trail on answers "which of the three places"
  (section 8) from the dump alone; (b) the trail's counter line in the very first walk gives the title's rate of AJM
  instance creates. If it stays far below 16,384 in 620 s the id-wrap candidate is out and `KYTY_BC5_AJM_LIVE_IDS`
  leaves tJ; if a fault's dump shows no AJM buffer near the bad record, tJ is dropped and its walks go to tA and tP.
- A fault in tP would clear `APR_POSIX=direct`; a fault in tJ would clear both AJM candidates. Those are the two
  results one night can give with certainty.

## Before the chain

The private acceptance of T (the slot's step 3 in `test-build.md`) passes first, with every switch unset. A build
that does not compile or fails acceptance is not walked.

## Agreed with the guardian (its answer of 2026-11-14, laptop only)

- **A fourth arm, tD**, at the guardian's cost (a quarter of the walks). No heap arm (bd412) in the night: it can end
  in a GPU write fault, which stops the chain, and heaps stay behind the top session's own GO.
- **The runner is the guardian's:** `night0412t.sh`, derived by a generator from `night0412i.sh` / `j` (the named
  exception for the CPU fault at eboot+0x1b349f, dry-tested against n10F2's and n10F1's files; a words file per arm;
  the stop file). Arms as rows (tag prefix, extra words). It writes under `~/bc5-work/exp0412/n8`.
- **Its log-only set stays on in every arm.** Its caution, not measured: the hang has not come in 16 walks with
  that set on b413a916 against 1 in 8 without it on f8cb77ad (chance about one time in eight), so dc412's work per
  submit hiding the hang is not excluded. If that is to be separated, the way is one more arm (tA with
  `BC5_DISPATCH_COUNT=0`), not dropping dc412 everywhere. Not added here: a fifth arm takes walks from the four; the
  top session's call.
- **Open, for the top session:** today's runner stops at the FIRST kernel line (R55). "60 walks or 3 GPU hangs"
  therefore needs the top session's word that the chain may go on after a hang whose reset succeeded; without it the
  chain stops at the first hang and is restarted by hand, and the count is summed over restarts (as
  `f403-f813-series.md` already assumes).
- **Owed to the guardian after T is built:** the path of T's binary and of its md5, the words file's path and md5,
  and the launcher T's walks use.

## The top session's decisions (2026-11-14, after the agreement above; these replace what differs)

1. **R55 stands.** The runner stops at the first kernel GPU line, also after a successful reset. No "3 GPU hangs"
   rule: after a stop the files are read and reported, and the chain is resumed only on the top session's GO; the
   count is summed over resumptions. (The restart of 03:25 came on a boot that had had a reset before.)
2. **No fifth arm.** In arm tA `BC5_DISPATCH_COUNT` alternates 1 / 0 (odd / even walks of tA), as in the guardian's
   n10 chain; in tJ, tP and tD dc412 is on. tA's two halves are reported apart.
3. **The series ends** when 60 walks are done, at 07:00, or on the maintainer's word that he wants the box (the stop
   file, after the walk in progress), whichever comes first. The order tA tJ tP tD is kept so that an interruption
   leaves equal counts.
