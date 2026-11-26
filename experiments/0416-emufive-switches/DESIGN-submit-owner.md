# Design note: a submit-owner thread (`BC5_DIRECT_SUBMIT_OWNER=1`, default off)

Status: a note for review, no code. Source of the idea: KytyPS5 `graphicsRun.cpp:112-133, 372-480 @589bd14` (exp 0414
section 3.3): submitters only enqueue; one GPU thread owns the device work. Numbers: exp 0412 sections 20–22.

## The problem, as measured

Every submitting thread (`bc5-ring`, the Render Thread, `bc5-chainwd`) runs `submit_now` under `g_dev_mutex`: probe,
mapping sync, learned windows, filters, the CS ioctl. The mutex is held 45 % of wall time; waits add up to 35 s in
180 s; single holds are 35–135 ms with peaks of 354–1,501 ms; the long holds are mapping maintenance; they cover 27 %
of the frame gaps over 100 ms, 44 % in play.

## Proposal

1. **Submitters stop at an enqueue.** Work that needs only the buffer (the probe, the filters, hint collection) runs on
   the submitting thread with no lock. The result is a `Submission` (the IB list, its fence slot, its soft-CP marks,
   the ring it wants) pushed to a queue under a short queue mutex.
2. **One thread, `bc5-submit`, owns `g_dev`.** It takes submissions in enqueue order and does the mapping sync, the
   release cuts and the CS ioctl. Per-ring order and the in-flight cap stay as they are.
3. **Blocking calls keep their meaning.** A caller that today returns after the ioctl (and may wait on the fence) waits
   on its submission's own completion flag instead. A chain flush, wait-idle and an event-queue wait become "enqueue,
   then wait for my entry".
4. **A submission that cannot go yet is put back at the front, not slept on** (KytyPS5's `blocked` path), so a held
   chain does not stop a ready compute buffer.

## What it does not change

The owner still does the same work serially, so GPU time and total CPU time are the same. The gain is that the Render
Thread no longer waits behind another thread's mapping sync. Expected: bounded by the 27–44 % share of gap time; a few
percent in mean fps, more in the hitch count.

## Risks and open points

- **Order.** Today the mutex gives a total order of submissions and of the map/unmap calls between them. With a queue,
  a guest unmap must not run before a queued submission that uses the range. KytyPS5 sends unmaps through the same
  queue (`SendCommand`); ours would need the same: the release cuts and unmaps become queue entries.
- **The soft-CP replay** reads guest buffers by address after the submission (the EOP ring bug Codex found is this
  class). Every host-built packet must be owned by its entry; guest buffers must stay valid until their entry is done.
- **Failure path.** A failed ioctl today is seen by the submitting thread at once; it must still get the result.
- **Zero skip and the ledger** (exp 0412 section 47) touch the mapping state at submit time; they must run on the owner.
- **Locks held across the wait.** A submitter that waits for its entry while holding a guest-visible lock is the
  convoy again; the callers of `submit_now` need an audit first.

## Order of work

1. Audit of the callers of `submit_now` and of everything that takes `g_dev_mutex` (a table: who, why, what it reads).
2. A CPU model with stand-ins (queue, owner, blocked entries, unmap entries) and an order test.
3. The switch, default off, in a private build; measured on the load-and-fps session's route (0415) against the
   hold-time and gap counters of exp 0412.

Size L. It is stages 1–2 of the device-mutex design with a different owner model, so it goes through its own review
before any code.
