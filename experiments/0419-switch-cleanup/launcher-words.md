# Experiment 0419: the launcher words that were never settled, one by one

The maintainer, 2026-11-13: "Słowa z launchera nigdy nierozstrzygnięte => po kolei do analizy na nowo". For each word:
what the code of candidate F does with it today, whether it can act on one ring, what its experiment said, and a
proposal. The code reading is of F's unit (`bc5LleAgc.cpp` 59d17cf5; line numbers are that file's) and of
`backend/src/direct.cpp`; a subagent traced it and the deciding lines were read again by hand. Nothing here is a run.

**One ring, always.** `compute_ring_env()` returns `kGfxRing` (-1) when `BC5_DIRECT_COMPUTE_RING` is unset
(unit 6744-6745), `acb_ring()` then returns -1 (6753), and F removes that word from the environment at process
start (`kIgnored`). So every job goes to the GFX ring and `comp` in `Device::submit` is always false.

| Word (launcher value) | What it does in the code today | On one ring | What the experiment said | Proposal |
|---|---|---|---|---|
| `BC5_DIRECT_CROSS_RING_WAITS` (`all`) | read at 8588; used at 8629 (`last->ring != ring && ...`: both rings are -1, the test never reaches the word) and at 8913 (`two_rings = ... && compute_ring_env() >= 0 && ...`: false) | **dead** | exp 0129: with compute buffers on ring 0 the start screen went from 32-34 to 41-42 fps; since exp 0342 (F412, F415) everything is on one ring | **delete** the word, its reader and the `two_rings` block |
| `BC5_DIRECT_RING_DEPS` (`dcb`) | read at 2207, handed to the backend (`set_ring_deps`); the one use (direct.cpp 1579-1589) collects the compute rings' last sequence numbers, which stay 0 because nothing is ever submitted there (1607): the request is the same as without the word | **dead** | exp 0323 (F385): removed the two-ring hang 11 of 11; on one ring there is nothing to order | **delete** (the unit's reader now; the backend's `set_ring_deps` with the next backend change) |
| `BC5_DIRECT_TWO_RING_WAIT_MS` (`4`) | read at 8947, inside the `two_rings` block only | **dead** (the read itself never runs) | exp 0133: 4 ms measured on ASTRO BOT on two rings (32-34 against 30-31 fps) | **delete** with the block |
| `BC5_DIRECT_CHAIN_HOLD_US` (unset) | read at 7012: how long a game thread's chain may stay open before it is submitted; unset = 2,000 us. Live whenever `BC5_DIRECT_CHAIN` is 2 or more (a general default in F) | **live**, at its built-in value | exps 0165, 0360, 0381 mention it; no run ever varied it | his decision: make 2,000 us a **constant** (the word goes, nothing changes), or keep the word for one arm at another value first |
| `BC5_DIRECT_DCB_WAIT_MS` (unset) | read at 8860: how long the game thread polls for an unsatisfied wait of a draw buffer before it gives up; unset = 8 ms, `0` = no wait | **live**, at its built-in value; the code's own comment says it exists for the single ring | exp 0026 (F64) and F263-F271 use it; no verdict on the value | the same choice: **constant 8 ms**, or one arm first |
| `BC5_DIRECT_LAZY_RELEASE` (`30,eager`) + `BC5_GUARD_SPLIT` (`1`) | parsed at 3180: in every sync of the direct memory it re-imports released chunks a view covers again and, once per period, cuts chunks idle for 30 s out of their buffers; `eager` also allows chunks under eager views; SPLIT (5801) allows cutting part of a buffer while aliases are on and re-applies the aliases at once | **live** (not ring-related) | exp 0401 e7 and exp 0412 (audit row B15): 16-31 cuts a run, no fault, 0.1-0.2 GiB; one arm cut 1,548 MiB and 96 % came back; "small gain, needed to keep the pin down" | with exp 0412: one arm without the pair on the second title (pin, orphans, available), then a constant or a delete; **not deleted without the maintainer's decision** |
| `BC5_DIRECT_HEAP_GUARDS` (unset = on) | read at 5933: only the exact text `0` turns it off. On: behind every eager heap of 32 MiB or more a 2 MiB zero buffer is mapped, so a GPU read just past the heap's end reads zeros instead of faulting | **live**, on | exp 0417 (F820): the guard of exp 0037 kept behind this word when the learned windows went; the scripted route was clean with and without, two runs each | by the maintainer's rule on GPU faults a guard that turns a fault into zeros hides a bug; proposal: one long arm with `0` on both titles, and if no fault record names a read behind a heap, the guards and the word go; **his decision** |

## Summary

- Dead on one ring, deleted in the next candidate without a run: `BC5_DIRECT_CROSS_RING_WAITS`, `BC5_DIRECT_RING_DEPS`,
  `BC5_DIRECT_TWO_RING_WAIT_MS` (the top session: "martwe trzy możesz kasować").
- Live at a value nobody ever changed: `BC5_DIRECT_CHAIN_HOLD_US` (2 ms), `BC5_DIRECT_DCB_WAIT_MS` (8 ms): a constant,
  on his word.
- Live and changing behaviour: `BC5_DIRECT_LAZY_RELEASE` + `BC5_GUARD_SPLIT`, `BC5_DIRECT_HEAP_GUARDS`: one arm each
  "without", read with exp 0412, then his word.
- Also from the launcher and settled elsewhere: `BC5_DIRECT_CP_COHER_START_DELAY` (exp 0418's table writes it always;
  the word is read by nothing in F).
