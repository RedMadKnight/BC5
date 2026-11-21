# q438: per-slot submit queue (BC5_0438_SUBMITQ=1; offline only)

`python -I mkq438.py ../bake438.cpp q438.cpp`: IN `ff9e8fe2`, OUT `bbd604f0f91d1592e2f1bdf66e8cb643` (gitignored).
`mkq438.py` `54be779f…`, `test_q438.cpp` `dd9f1c0f…`, `test_q438.sh` `b3986792…`.

**Ring-order fix (the 0438 session's reproduction: 3 of 11 random runs missed).**
- An earlier entry's real write got a later `order` than a queued entry's early write, so `ring_will_satisfy` took the older value as last.
- `register_label_writes` now renumbers queued early writes of its labels after it (switch on).
- `det order` gates it; `no-order` fails.

**Test** (`bash test_q438.sh`, VS clang++, all PASS):
- The cut blocks only gain lines. With the switch unset, `=0` or `=2`, the identity trace equals the bake unit's.
- random, 30 runs: 0 misses each, take order kept.
- Off path: 27–32 of 431 waits miss a writer; 0–2 of 20 drains are short.
- det: FIFO, union/f16_done per entry, early wait, order, BUG line, full queue, nested, flush_all(5)/(8), sync, destroy.
- 5 planted bugs caught.

**Deviations from today:**
1. Observe (why 8) waits for the drain too.
2. The tail takes `s.mu` by try_lock (hold_release may hold it while waiting for an early writer). Flight sets, f16_done and replays can lag.
3. f16_phase goes to 0 at return. F16's waiter (`ho430`, not tested) also needs the label gone from the union.
4. Nested flush: only if `s.mu` is free and there is no hold, otherwise skipped. It joins the union.
5. Early scan: every top-level packet, ring = chain ring, independent of EARLYREG.
6. `t_ui_*` stay on the owner.

**Open risks (reasoned):**
- Windows test stops the submitter at scope end (TLS-destructor join under the loader lock); glibc, TODO(verify).
- A cycle: early-writer wait behind back-pressure.
- r438's own early entries can still be passed.
- g_plw trim / m11 reset; join at exit; g_stage change.
