# 0065 — the render-target hint pass without a map and a linear walk

**Question.** The host's hint pass (`hint_targets`, patch 0001) maps windows around render targets
before the GPU faults on them. It cost the game's thread 0.6 ms a frame in ASTRO BOT's later
level (0064). Where does that go?

**Setup.** Per submission, the pass:
- copied the device's whole mapping list (~500 entries);
- checked each register table (~145 `LOAD_CONTEXT_REG_INDEX` per main buffer) with a linear walk
  over it;
- kept the context registers it follows in a `std::map`;
- after every change of a followed register, re-evaluated all 37 target bases, about 100 map
  lookups.

The change (`hints.py`), with the same results:
- the registers in a flat table (`HintCtx`);
- the bases re-evaluated only when a base register changed (a size changes no target);
- the table checks against the sorted mapping list with the binary search of exp. 0027
  (`covered_sorted`);
- the full list fetched only when a window is about to be mapped.

Run 292 (2026-10-13) against run 290: the scene and window of 0061. Raw data is in
`raw/runs-290-292.txt`.

**Result.**

| | run 290 | run 292 |
|---|---|---|
| fps | 43.6 | **44.2** |
| hints | 0.6 ms a frame | 0.3 ms |
| game thread inside the host | 5.8 ms | 5.5 ms |
| hint windows journaled in the run | 232 | 231 |
| timeouts | 0 | 0 |

**Verdict.** Passed: the pass costs half. It maps what it did before, judging by the windows it
journals. The later level gains 1.5%.

What is left on the game's thread per frame:
- prepare 3.1 ms (filter 1.8, tracker 0.6, copy 0.4);
- CS ioctls 1.5 ms (9 calls, each validating ~240 BOs in the kernel);
- label waits 0.4 ms;
- hints 0.3 ms.
