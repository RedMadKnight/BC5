# Review of `DESIGN-submit-owner.md` by exp 0415's session (2026-11-13)

The note is `../0416-emufive-switches/DESIGN-submit-owner.md`. The reviewer owns the lock side
(`../0415-load-times-fps/DESIGN-lock-side.md`, stages S1-S5). Measured numbers are from exp 0415's README sections 8,
10 and 13; what is the reviewer's reading is marked so. Recorded here by exp 0417's session from the reviewer's
message; shortened, nothing added.

## Fit and overlap

- The note aims at the same wait as S2-S5 and needs S1 as its base: its first risk, "unmaps must become queue
  entries", is the change records, which S1 showed complete and in order for the view list (7,991 comparisons over
  866,732 records, 0 mismatches, both titles).
- Both designs add one thread that owns mapping state (the note's `bc5-submit`, S4's applier). Built apart they would
  be two owners of the same tables. They are one design: a single owner that takes change records and submissions in
  one sequence order gives the ordering by construction. So the note is the step after S4, not a rival.
- What S2-S5 already remove: S2 and S3 shrink the maintenance (views 0.9-1.9 s, mappings 0.9-1.3 s per phase), S4
  takes the import's kernel work out of the hold (1.6-2.2 s of a menu load), S5 the `/proc/self/maps` read (1.8-2.0 s
  per 34 s of play), and the learned windows (1.2-2.7 s per phase) go with exp 0412's rule. That is the 68 % of the
  menu load's hold. What stays for an owner is the device call: 2.6-4.7 s per menu load, 6.0-7.1 s per 34 s of play.

## What is wrong or unsafe in the note

1. **The premise is dated.** The note's numbers (holds of 35-135 ms, long holds are mapping maintenance) are from the
   orphan-release runs. In exp 0415's split the maintenance is a full re-derivation on most submissions: 540-860 full
   syncs per phase, because the guest's ranges change 620-5,500 times a second. An owner does the same work serially;
   entries then wait in its queue instead of threads waiting on the mutex. Only a submitter that does not need its own
   entry's result gains.
2. **Point 1 is unsafe as written.** The probe, the filter and the state tracker are not buffer-only: the probe
   decides a forced sync against the mapping set of that moment; the filter drops packets whose operands are unmapped
   and reads the device's sorted mappings; the state prefix depends on what the previous job left on that ring, in
   order. They can run early only against a snapshot with a generation recheck at the entry's turn, and in ring order
   (exp 0412's stage 2, with its "waits for the pin in flight" rule).
3. **Point 4 changes cross-ring order.** A blocked entry going back to the front while others pass is what
   `BC5_DIRECT_RING_DEPS=dcb` exists to prevent (exp 0323, F385: 11 of 11 hangs with RT on). Any passing rule has to
   be written against the ring dependencies and keep their catcher.
4. **Point 3 keeps the waits that matter.** In play the Render Thread's submissions end in a flip drain or a label
   wait; a chain flush "at a wait" is the most common flush reason (exp 0412 section 26). Those callers wait for their
   entry behind everything the owner has queued, so their time does not change; they save only their own prepare and
   ioctl CPU if those move (prepare 3.4 s and CS 3.3 s per 34 s of play, over three threads).
5. **Capacity** (inferred from the hold by part): an owner doing sync, list and CS would be busy about 55-60 % of the
   time in a menu load and about 35 % in play if prepare stays with the submitters. That fits one thread, but in the
   slower session's run (19.1 s held of 39 s) there is little room, and a queue behind a saturated owner is a new
   source of long frames.
6. **What L3 taught.** Removing 0.4-0.9 s of hold per phase moved no load time and no frame rate that could be
   measured. A design whose gain is "the wait, not the work" should say which waits, measured, before code.

## Verdict of the review

Not dropped, not built apart: **a later stage of the lock side, after S2-S4** ("the applier of change records also
owns the CS ioctl"), with the record queue as its unmap ordering.

To measure first, with counters and no change of behaviour:
1. the mutex wait per thread, split by what the thread does next: needs its own entry's result within a few ms (flip
   drain, label wait, chain flush at a wait) against returns to the title. Only the second kind is avoidable by an owner;
2. the queue the owner would have had: per second, submissions arrived against the hold time they needed (from the
   hold-by-part stamps), to see whether it would back up in the loads;
3. the table of every caller of `submit_now` and every holder of `g_dev_mutex` with what it reads. S4 needs the same
   table for its lock order, so one table serves both.

## Two notes on the integration's runs (the same message)

- The route times that did not move between the APR default and `=0` (save list at 93-94 s, G at 117-119 s) are the
  runner's gate, not the game: exp 0413's runner sends its first key at 85 s or later, about 35 s after the start
  screen is up, so a menu load that ends 7 s earlier cannot show there. exp 0415's runner sends the key when the start
  screen runs (from 12 s on); then the first key lands at 50.3 s against 57.6 s. Without a route: the line "6 GiB of
  APR data read at" in the `KYTY_BC5_LOAD_STAT` file.
- The lower available memory with `=0` fits the doubled disk reads going through the page cache; exp 0415 has no
  measurement of that.
