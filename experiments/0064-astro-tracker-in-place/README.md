# 0064 — the state-stack tracker in place

**Question.** After experiment 0063, the remaining lever is the work on the game's thread itself.
The state-stack tracker (exp. 0016, F35) took 0.8–0.9 ms a frame in the later level. Where does
that go, and what does a cheaper version give?

**Setup.** `bc5::state_stack::Tracker::apply` rebuilt the whole filtered IB into a new vector, one
`push_back` per dword: ~355,000 dwords a frame. Yet it changes a buffer only at a context pop.

- `Tracker::apply_in_place`: the filtered IB stays where it is and is rebuilt only when a pop
  inserts packets, by ranges. `apply` is now a copy plus `apply_in_place`. `Device::submit` and
  `prepare-bench` use the in-place form.
- `Device::Impl::main_buf`: the filtered main IB is kept between submissions instead of a fresh,
  zeroed vector per buffer.

Checks:
- ctest 40/40, including the tracker's push/pop tests through `apply`;
- `prepare-bench --hash --no-mapped` over the 60 dumped buffers of 0061 (filter + tracker + CU
  tables + copy): the same output before and after, on buffers with pops too.

Live (2026-10-13), the scene and window of 0061 (later level, 55–135 s after the load, Astro at
the wall), with the settings of run 282:
- run 290: the tracker in place;
- run 291: also the kept buffer.

Raw data is in `raw/runs-282-291.txt`.

**Result.**

| | run 282 (0061) | run 290 | run 291 |
|---|---|---|---|
| fps | 41.7 | **43.6** | 43.6 |
| frame, mean / p90 | 24.0 / 26.2 ms | 22.9 / 25.5 | 23.0 / 25.6 |
| game thread inside the host | 6.3 ms | 5.8 | 5.9 |
| prepare | 3.5 ms | 3.1 | 3.2 |
| tracker | 0.93 ms | 0.61 | 0.60 |
| waits given up, timeouts | 0, 0 | 0, 0 | 1, 0 |

Offline, the tracker on the 110,015-dword buffer (two pops): 0.102 → 0.045 ms.

**Verdict.** Passed for the tracker: +4.6% in the later level, the same bytes on the GPU. The kept
buffer gives nothing measurable. glibc stops mapping chunks of that size afresh after the first
free, so there was little to save. It stays, as it is simpler for the allocator. ASTRO BOT's later
level now runs at 43.6 fps, from 34.9 at the start of experiment 0061.
