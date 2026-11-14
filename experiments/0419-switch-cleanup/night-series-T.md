# The night series on the test build T: arms (proposal of 2026-11-14, to be agreed with the guardian; nothing run)

Asked by the top session. T is `test-build.md` (patch 5f2df896, not built yet). The series is the long walk of the
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

Order: tA tJ tP, repeated, so that a drift of the box cannot pose as an effect. One build, one lock line for the
chain, a stop file checked between arms and tested dry before the first walk.

## Stop rule (LESSONS R55)

The chain stops before the next arm after any kernel GPU line, a new fault record, or an unknown end, also when the
reset succeeded. **One named exception, written here by the top session's order:** the title's CPU fault at
eboot+0x1b349f (exit 65, an access violation whose crash text names that address, 0 kernel lines, no new fault
record) does not stop the chain: it is the event the series is looking for. Any other guest fault stops it.

## Size, and what the series can and cannot show

- Fixed before the start: 60 walks (20 per arm) or 3 GPU hangs, whichever comes first; the same 60 walks are the
  count of `f403-f813-series.md`, with the arms kept apart in the table.
- The CPU fault has come 2 times in about 36 long walks of the F family (12 of this experiment, 26 of the guardian's
  on b413a916 by its section 93, less the two that faulted). At that rate 20 walks of one arm show it once on
  average, and 0 of 20 against 1 or 2 of 20 separates nothing. **The arms give a direction, not a verdict.**
- What does decide something: (a) one fault in any arm with the trail on answers "which of the three places"
  (section 8) from the dump alone; (b) the trail's counter line in the very first walk gives the title's rate of AJM
  instance creates. If it stays far below 16,384 in 620 s the id-wrap candidate is out and `KYTY_BC5_AJM_LIVE_IDS`
  leaves tJ; if a fault's dump shows no AJM buffer near the bad record, tJ is dropped and its walks go to tA and tP.
- A fault in tP would clear `APR_POSIX=direct`; a fault in tJ would clear both AJM candidates. Those are the two
  results one night can give with certainty.

## Before the chain

The private acceptance of T (the slot's step 3 in `test-build.md`) passes first, with every switch unset. A build
that does not compile or fails acceptance is not walked.
