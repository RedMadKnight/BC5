# ADR 0010 — A queue's consecutive buffers in one kernel submission

**Status:** proposed (2026-10-19), measured in experiment 0163 (F213: the ring thread's buffers
chain, the game thread's do not — one `dcb` per ioctl, each with `COND_EXEC`), extended the same
day with §A (a `COND_EXEC` closes nothing any more) and §B (a chain across the game thread's
ioctls), measured in experiment 0165. Off by default (`BC5_DIRECT_CHAIN=1`: the chains of one
call; `=2`: also across the game thread's ioctls, §B); nothing of it is in the play settings until
the experiments have a verdict. Hard rule 5 applies: it changes nothing without the direct path's
own switches.

## Context

- The console's command processor reads the title's rings itself: a buffer costs the CPU what
  writing it costs, and the title's render thread is free for the title's work
  (`docs/console-vs-host.md` §3).
- The host turns every buffer into one kernel command submission (ADR 0005 §3): the second
  title submits 4,000–5,000 buffers a second, ~130 a frame (59 jobs from the game thread, 74–79
  from the ring thread), and its `Render Thread` spends three quarters of its time in that path
  — the IB copies, the CS ioctl, `Device::submit`, the mapping sync, the trackers (experiment
  0162, F210). The title asks for 60 fps and gets 30–42.
- What a submission costs is mostly fixed per submission, not per dword: the mapping sync and
  the hint pass (`submit_one`), the lazy-sync probe (a filter pass of its own for light buffers),
  the policy filter, the state trackers, the nested survey, the BO list, the CS ioctl and the
  fence (`Device::submit`), the completion item (experiment 0162: `prepare 6–7 ms, cs 4.5–5.1 ms`
  of the game thread's 12–13.6 ms inside the host per frame).
- The buffers come in groups already. The game thread hands them over per `/dev/gc` ioctl: the
  submit header (`cc` + three `hib`), then a submit list or a submit(+eop) of several `dcb`s. The
  ring thread takes a slice of a doorbell queue per poll: the `acb`s rung since the last poll
  whose waits are satisfied (in the menu of run 0817: `cc 3, hib 150, hib 2`, `dcb 96, 199, 16`,
  `acb 2, 120, 2, 16` per queue and frame). The console runs each group as one stream.
- Experiment 0118 found a hazard of the per-buffer form that a chain removes: a host prefix
  submitted as a job of its own let the ring thread interleave between prefix and buffer, and the
  buffer ran with the other queue's state (two machine-downs).

## Decision

1. **A chain is the run of buffers one call into the direct path hands over without a CPU-side
   wait between them**, on one thread: on the game thread the buffers of one submit ioctl; on
   the ring thread the ACBs of one poll slice of one queue. Host-built prefixes (`acb-state`,
   `dcb-state`, the full-state prefix of a piece) join the chain in front of their buffer.
2. **One scratch IB per chain.** The segments' dwords are laid end to end and the chain goes
   through `Device::submit` unchanged: one filter pass, one tracker pass, one nested survey, one
   BO list, one CS, one fence, one completion item. No `INDIRECT_BUFFER` packet per segment (the
   CP would fetch the same dwords through one more level for nothing; the console's own
   `INDIRECT_BUFFER` targets are still copied behind the chain as today) and no multi-IB CS (the
   kernel's per-IB work would stay per buffer; the gain is in doing the host's and the kernel's
   work once).
3. **The chain is closed (submitted) when:**
   - the call ends (the ioctl returns; the slice is submitted) — `chain_end()`;
   - a wait inside a buffer has to be served on the CPU (what precedes it goes first, as the
     pieces of ADR 0008 do; the polling loop reads what the GPU writes, and a label the chain
     would write must not be awaited before the chain is on the ring);
   - the next buffer needs another kernel ring (ADR 0009: the ring thread's ACBs by `acb_ring`)
     or another GDS setting, or is of the other class (graphics `cc/hib/dcb` against compute
     `acb`): the chain's kind is `dcb` or `acb`, and the host's per-buffer checks (indirect
     arguments, skipped programs, the carried CP state of F209) run over the chain in stream
     order with that kind;
   - ~~a segment holds `COND_EXEC`~~ — no longer, since §A: a `COND_EXEC` only closes a chain when
     its skip count runs past the end of its own buffer (a malformed buffer; counted, submitted
     alone);
   - the chain would exceed 1 Mi dwords (the scratch slot grows to the chain's size once);
   - an instrumented copy is wanted (the GE probe, `BC5_DIRECT_UCONFIG_FORCE`,
     `BC5_DIRECT_INDEX_BASE_DUP`, `BC5_DIRECT_INDEX_TYPE_MASK`: diagnostics with their own offset
     maps) — those buffers go alone through the old path.
4. **The soft CP sees per-buffer marks as before.** `Device::submit` returns the executed offsets
   of the chain; the host splits them back per segment (`set_gpu_executed` on the title's own
   buffer, a prefix's dwords skipped — what `alias_gpu_executed` did for a prefixed piece). The
   soft-CP replays of an ioctl's buffers are posted after the chain's fence item, in order, each
   with the chain's marks (the lookup is by address range, so one set serves all). The ring
   thread keeps its own order: slice, `chain_end()`, marks, post.
5. **Kept per buffer, unchanged:** the full-state tracking before `submit_split` (`piece_check`),
   the split at CPU-side waits and its prefixes, the ACB readiness gate and tail split (its head
   is submitted and the chain closed at once), the crash journal (one line per chain, the
   segments counted).

## What is not chained, and why

- A buffer whose wait is served on the CPU splits the chain at the wait (above). The console
  blocks the queue there; the host cannot, with one ring per class.
- ~~A buffer with `COND_EXEC`~~: §A.
- Buffers of different rings, GDS settings or classes.
- Across calls: with `BC5_DIRECT_CHAIN=1` a chain never outlives the ioctl or the poll slice that
  opened it; `=2` holds the game thread's chain across its ioctls, §B. The ring thread's slices
  stay per poll in both modes (a slice is already the run of ACBs whose waits are satisfied, and
  the consumer's own waits poll labels the graphics chain writes).
- Copying less: the title's buffers are mapped 1:1, but the scratch copy is where the filter's
  verdicts (NOPs, CU masks, the re-pointed `INDIRECT_BUFFER`s) are written, and the copy is padded
  to the CP's 32-byte fetch (experiment 0016: a fetch past a buffer's end hung the machine). A
  segment that passes the filter untouched could be executed in place from an `INDIRECT_BUFFER`
  packet in the chain; not in this step.

## A. `COND_EXEC` is segment-local: the three passes grow its count instead of giving up

**Why a chain closed around it.** `COND_EXEC` (PKT3 0x22, five dwords: header, flag address
lo/hi, control, exec count) tells the CP to skip the next *exec count* dwords of the same stream
when the flag is zero (layout as `backend/src/indirect_check.cpp` reads it, `ib[i + 4] & 0x3fff`;
experiment 0052 relied on it). A pass that inserts dwords inside that range must grow the count,
or the skip ends short and the CP runs the tail of what should have been skipped. Experiment 0052
made the CP DMA waits do that (`indirect_check::insert_before`: the IB's own counts grown by what
lands inside their ranges, the IB left unchanged if a count no longer fits its 14 bits), but two
older passes still gave up on the whole IB when they saw one, and a third gave up on the whole IB
when a grown count overflowed:

1. the backend's PFP_SYNC_ME before each GFX-form `DISPATCH_INDIRECT` (`Device::submit`,
   `has_cond_exec`, `backend/src/direct.cpp`; only without the GPU check, so not in the play
   settings);
2. the host's compute-form `DISPATCH_INDIRECT` rebuild for the GFX ring (experiment 0038,
   `mec_expand_ib` in `submit_now`, `bc5LleAgc.cpp`): with a `COND_EXEC` anywhere in the IB the
   rebuilt dispatches were dropped instead;
3. the backend's GPU check of indirect arguments (`indirect_check::apply`, experiment 0052; in the
   play settings): counts grown per range, but one range that no longer fits NOP-ed *every*
   checked dispatch of the IB.

In a chain the IB is several buffers, and every large `dcb` of the second title holds `COND_EXEC`
(F213), so one buffer's packet decided for all of them — which is why 0163 closed the chain
around it.

**Decision.** A `COND_EXEC`'s range lies inside its own buffer: its count is a dword distance
within the stream the title wrote, and the title cannot mean a skip into memory it did not write
(the next segment of our chain is another buffer at another address). So the three passes treat
each `COND_EXEC` by itself, in whatever IB it sits:

1. the PFP_SYNC_ME insertion goes through `insert_before` like the DMA waits: counts grown, no
   whole-IB exclusion; if a grown count would not fit, the IB keeps no PFP syncs (as before for an
   IB with `COND_EXEC`);
2. the host's rebuild maps every `COND_EXEC`'s range end through its old→new offset table and
   writes the grown count; a range whose grown count would not fit keeps its own rebuilt
   dispatches dropped (the old fallback, now per range, not per IB);
3. the GPU check's overflow fallback NOPs only the checked packets inside the ranges that no
   longer fit and reruns the pass over the rest (`indirect_check::apply`, with a unit test).

No segment list goes to the backend: with the counts grown per packet, the passes do not need to
know where a buffer ends. The host keeps one check at the chain (`chain_append`): a `COND_EXEC`
whose range runs past the end of its own buffer is malformed for this reasoning, and such a
buffer is still submitted alone (counted in the `chains:` journal line as `cond-past-end`). The
two `chain_flush(3)` calls of 0163 are gone. The other passes that grow an IB (the CU-mask
overrides, `cu_tables::apply`; the state stack, `state_stack`) already decide per range
(`conditional` in their statistics) and are unchanged.

**Hardware facts used.** The packet layout and the meaning of the count: `backend/src/
indirect_check.cpp` (`kOpCondExec`, the `Cond` ranges), as experiment 0052 ran it; the GFX7+ form
`PKT3(COND_EXEC, 3, 0)` the GPU check emits itself (`kCondExec` there). TODO(verify): the
`COND_EXEC` count field's width on gfx10 beyond the 14 bits the backend assumes (Mesa does not
emit the packet; the title's own packets fit).

## B. A chain across the game thread's ioctls (`BC5_DIRECT_CHAIN=2`)

**Why.** The game thread hands over one `dcb` per submit ioctl (F213: 59 jobs a frame, 1 buffer
per call), so a chain per call is one submission per buffer for it, and the render thread's cost
(F210) does not move. The console's CP reads the queue as the title fills it, and the title
learns that work is done only through what the GPU writes — labels, EOP events, the flip. So the
host may hold a game thread's buffers back as long as the title cannot have observed the GPU in
between, and submit them as one chain when it can.

**Decision.**

1. **The game thread's chain stays open at the end of a submit ioctl** (`chain_end()` submits
   nothing in mode 2 on a thread of source 0, `on_game_thread()`); the next ioctl's buffers are
   appended to it (the header's `cc` + `hib`s, the submit list's or the submit(+eop)'s `dcb`s,
   all of the graphics class on the GFX ring). The ring thread's slices close per poll as before.
2. **The chain is closed wherever the title can observe the GPU**, by `chain_flush`:
   - the flip: `SubmitEopFlip` → `Direct::drain()` (already `chain_flush(5)`; the flip is not
     deferred for this title, so the frame's jobs are waited for there too);
   - a wait served on the CPU inside a buffer (`submit_split`: `chain_flush(1)` before the label
     is polled, so that the chain's own label writes reach the ring first, and so that
     `ring_will_satisfy` can keep the wait for the GPU — the writes are registered at
     submission);
   - the gc ioctls "submit done" (0xc0048116) and "wait idle" (0xc0048117), and a wait on an event
     queue (`KernelWaitEqueue` through the gc `kevent` wrapper): the EOP events the title waits
     for are posted by the soft CP replay, which in mode 2 runs after the chain's fence (below);
     these points close every registered chain, not only the caller's, since the title's thread
     that observes may not be the one that submits;
   - a time bound: `BC5_DIRECT_CHAIN_HOLD_US` (default 2000) after the chain's first segment, a
     watchdog thread (`bc5-chainwd`) submits it if the owner has not. A title that polls a label
     in memory without calling the host (no ioctl, no sleep, no event wait) can only be served
     this way; the bound also caps what the ring thread's ACBs wait for when they poll a label
     the held graphics chain writes (its CPU-side waits only flush its own chain). The owner
     also closes an over-age chain itself at its next `chain_end()`;
   - as before: the ring/GDS/class change, 1 Mi dwords, the instrumented copies, a `COND_EXEC`
     past its buffer's end.
3. **Submission from a thread that is not the owner.** The chain carries what `submit_now`
   used to take from the owner's thread-local state: the waits kept for the GPU
   (`t_keep_waits`, converted to chain offsets when the segment is appended — they were cleared
   per buffer and would be lost across ioctls otherwise), the given-up flag per segment (0163).
   A chain is taken under its mutex and submitted under its flush lock, so that the owner's next
   flush waits for the watchdog's and the ring order holds; the watchdog skips a chain whose owner
   is inside `Direct::submit` (the owner flushes at its waits itself, and a buffer split at a wait
   must not have its head submitted from elsewhere between the pieces). The completion items and
   the soft-CP posts go to completion queue 0 whatever the thread (the watchdog's `t_cq` is 0).
4. **The soft CP replays after the chain's fence, in order.** In mode 1 a `dcb`'s replay runs on
   the game thread at the ioctl's end with the chain's marks (0163, `soft_posts_end`); across
   ioctls the marks exist only when the chain is submitted, which may be on another thread. So in
   mode 2 every replay of a game-thread buffer is posted to the completion queue behind the
   chain's fence item (what `submit_raw` always did and `BC5_DIRECT_SOFTCP_POST_IB=1` did for IB
   packets, experiment 0083: the EOP events then come when the GPU is done, as on the console),
   with the marks of every chain that carried a piece of the buffer. The marks accumulate on the
   chain (`Chain::marks`) and are cleared when the pending replays are posted while no buffer is
   in `Direct::submit`. `Direct::post` keeps the queue order, so a replay never runs before the
   job it describes and the replays of two chains run in submission order.
5. **Unchanged:** mode 1 and the ring thread (one chain per call, replays as in 0163); the
   per-buffer passes before the chain (`piece_check`, `submit_split`, the ACB gate); the backend.

**What a held chain costs.** The GPU starts the frame's first job up to one hold later than
today (the work is the same; the latency moves to the first submission of a group), and the
ring thread's ACBs that wait for a graphics label of the held chain poll up to that long. The
bound is the knob to measure; experiment 0165 compares `=1`, `=2` and off.

**What is still not chained.** A game-thread buffer whose wait is served on the CPU still splits
the chain at the wait (the head goes first); the ring thread's ACBs stay per slice; the diagnostic
copies go alone. The DMA snapshot (experiment 0122) is taken when the chain is submitted, up to
one hold after the title handed the buffer over: the title's staging ring is reused only after it
has seen the GPU finish (the labels it waits for are written by the submitted chain), so the copy
still sees what the title submitted; if a title reuses staging on the flip alone, the hold would
have to end at the flip's own ioctl, which it does (`drain`).

## Consequences

- The number of kernel submissions a frame falls from the number of buffers to the number of
  ioctls plus poll slices plus CPU-side splits; the per-submission work of `submit_one` and
  `Device::submit` falls with it. Measured in experiment 0163 (flips/s, the render thread's CPU).
- Faults are reported per chain: a timeout names the chain, and the timeout probe dumps the
  chain's IB; the segments' offsets are in the journal line.
- The journal's `submit #n kind dwords` lines count chains; `submitcost.py` counts them as
  submissions, so it measures the gain directly.
