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
