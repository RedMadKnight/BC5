# ADR 0010 — A queue's consecutive buffers in one kernel submission

**Status:** proposed (2026-10-19), measured in experiment 0163 (F213: the ring thread's buffers
chain, the game thread's do not — one `dcb` per ioctl, each with `COND_EXEC`; next steps there).
Off by default
(`BC5_DIRECT_CHAIN=1` turns it on); nothing of it is in the play settings until the experiment
has a verdict. Hard rule 5 applies: it changes nothing without the direct path's own switches.

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
   - a segment holds `COND_EXEC` (its skip counts are dword offsets; the host's insertions are
     grown around them per IB, and the PFP sync insertion gives up on an IB with one): such a
     buffer is submitted alone, as today;
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
- A buffer with `COND_EXEC`, until the insertion passes map offsets per segment.
- Buffers of different rings, GDS settings or classes.
- Across calls: a chain never outlives the ioctl or the poll slice that opened it. A chain held
  open until the next call would have to be closed on every label read, flip and wait of the
  title (it polls labels the chain writes), which is the next step if this one is not enough.
- Copying less: the title's buffers are mapped 1:1, but the scratch copy is where the filter's
  verdicts (NOPs, CU masks, the re-pointed `INDIRECT_BUFFER`s) are written, and the copy is padded
  to the CP's 32-byte fetch (experiment 0016: a fetch past a buffer's end hung the machine). A
  segment that passes the filter untouched could be executed in place from an `INDIRECT_BUFFER`
  packet in the chain; not in this step.

## Consequences

- The number of kernel submissions a frame falls from the number of buffers to the number of
  ioctls plus poll slices plus CPU-side splits; the per-submission work of `submit_one` and
  `Device::submit` falls with it. Measured in experiment 0163 (flips/s, the render thread's CPU).
- Faults are reported per chain: a timeout names the chain, and the timeout probe dumps the
  chain's IB; the segments' offsets are in the journal line.
- The journal's `submit #n kind dwords` lines count chains; `submitcost.py` counts them as
  submissions, so it measures the gain directly.
