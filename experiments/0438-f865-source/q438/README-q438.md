# q438: per-slot submit queue (BC5_0438_SUBMITQ=1; offline only)

`mkq438.py` takes the bake unit `ff9e8fe2` → `q438.cpp` `20112972`, or A2's `0402a183` → `q438a2.cpp` `b8de84c5` (both gitignored).

**Test** (`bash test_q438.sh UNIT INPUT`; both units PASS):
- Cut blocks only gain lines. Identity with the switch unset, `=0` or `=2` equals the input's.
- 30 random runs, 0 misses (off: 27–35 of 431).
- det: 13 cases. Planted bugs: 6, all caught.

**Fixes:** queued early writes stay after later real writes in g_plw (`det order`). The trim keeps early entries (`det trim`).

**Checked:**
- a. A held submitter only delays the wait. The wait ends at the real write or the BUG-lined removal, at r438's existing compare-only 100-ms BUG lines (`det backpressure`: 350 ms, 3 lines).
- b. `~ChainSlot` joins only the exiting thread's submitter (`det destroy`).
  - `_exit(86)` skips it.
  - glibc `exit()` runs TLS destructors before the static ones, with completion threads alive.
  - A reopen (11839–11845) is serialized by `g_dev_mutex`, as for bc5-chainwd today.
- c. Fixed (above).
- d. Cannot happen: `g_stage` is set only in `init_once_locked` (2267, 2276) before any chain; `chain_on` (7911) needs `All`.

**Deviations:**
1. Observe (why 8) waits for the drain.
2. The tail takes `s.mu` by try_lock, so union, f16_done and replays may lag.
3. f16_phase goes to 0 at return. F16's waiter (`ho430`, untested) needs the label out of the union.
4. A nested flush is skipped when `s.mu` is busy or a hold exists.
5. The early scan covers every top-level packet.

**Open:**
- One unexplained 200-ms early-writer wait in 90 runs; the writer was found. Scheduling is suspected.
- The Windows test stops the submitter at scope end, because of a loader-lock join.
- r438's own reorder hole: fixed separately in `../r438o`.

**The slow stub submit_now (the >100-ms waits in 5 of 60 random runs; explained 2026-11-21, a stub artifact):**

- Per-phase maxima in the stub (slot lock, gate, preparation sleep, `register_label_writes`) put the whole time in the preparation sleep.
  - It asked for 100–300 µs and took 16–64 ms: Windows rounds `sleep_for` up to its 15.6-ms timer tick.
  - The slot lock stayed at or under 0.06 ms, the gate under 0.03 ms, and `register_label_writes` under 1 ms (once 27 ms, scheduling).
- A game-thread wait on a queued entry waits for every entry ahead of it, one tick each, plus scheduling. That gave 100–470 ms, past r438's 100-ms BUG line.
  - One failing run had a 128-ms wait while its longest single submit_now was 17 ms: the queue, not one call.
- With Windows' timer at 1 ms (`Q438_TIMER1=1`, now the script's default), two passes of 30 runs each (q438.cpp and q438a2.cpp) gave 0 BUG lines in 58 of 58 runs and rc 0.
  - The longest early-writer wait was 4–6 ms, with one 21.7 ms and one 47 ms outlier under laptop load.
  - The longest submit_now was about 2.5 ms.
- On Linux the stub's sleeps are sub-millisecond, so this is not a property of Q438.
- On the box a long wait comes only from a real submit_now held by GPU back-pressure or a recovery. That is what r438's BUG line is there to show (risk a).

## mkq438x.py: labelmap and q438ng (on stack438.cpp `29d02cb5` → `stack438x.cpp` `2c45a0d6`, gitignored)

**labelmap** (ASTRO BOT: 213 "never reached the ring" lines per SUBMITQ=1 run).
- The early scans took every label write. The filter NOPs a packet whose memory operand `opt.mapped` rejects, and only passed packets are registered for real.
- The filter's check is now `label_write_mapped` (moved, unchanged) and `lw_packet_mapped` (the filter's loop over `memory_operands`). `q438_scan` and `r438_scan` read them through one `sorted_mappings()` snapshot per scan; `r438_scan` only inside `r438_begin` (EARLYREG on).
- **Mapping changes between the scan and the submit:**
  - Mapped at the scan, unmapped at the submit: the BUG line at the entry's end stays. The GPU will not write the label either, so a wait that then finds no writer is the truth; the line marks a dropped title write.
  - Unmapped at the scan, mapped at the submit (for example by `submit_now`'s own sync): no early entry. Until the submit a game-thread wait sees no writer, the pre-r438 behaviour; it cannot hang. Registering it early would bring back the BUG lines for addresses that never map, as on ASTRO BOT. Open: count on the box how often a scan-unmapped write later registers.
- Cases: `det labelmap (i)`, `(iii a)`, `(iii b)`, and r438o's `lwm`. Planted `lwm-noscan` fails.

**q438ng** (the hang hypothesis): **reproduced**.
- Entry 1 is held in submit_now; entry 2, the writer of L, is queued behind it; L's memory holds a stale value that satisfies an acb wait.
- On bc5-ring, `ring_will_satisfy` skips early entries, and `acb_ready` (unit ~7665) passed the wait at once.
- At the submit, `ho430::at_wait` returned after its bounds (~55 ms) with the writer still queued, and the stale value passed the wait.
- **Fix:** `acb_wait_unready` (acb_ready's test, factored out) also holds the acb while a queued chain writes the label (`q438_writer_queued`). The acb is deferred as for any unready wait. After the writer's submission F4 orders it (`det q438ng`). Planted `ng-off` fails.
