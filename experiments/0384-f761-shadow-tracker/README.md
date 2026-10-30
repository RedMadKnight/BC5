# Experiment 0384: a shadow of the state tracker, with a contract the oracle can check

**Date.** 2026-10-30. **Where.** Laptop only: no box, no GPU, no game. **Base.** main d6fa368, backend `full_state.cpp` unmodified.
Branch `proto/f761-shadow`. A prototype in this directory; nothing in `backend/` or the host includes it.

## Question

F761: `full_state::Tracker` applies packets after an `INDIRECT_BUFFER` CHAIN, which the CP never runs, and Codex showed the wrong
value reaches `emit_prefix`. Exp 0381's plan answered with a contract and a Python model, and Codex's review (`F761-PLAN-REVIEW.md`)
found two gaps. Can a separate shadow state hold that contract in C++, on real PM4 dwords, with a boundary contract for
`COND_EXEC`, while the old tracker's bytes stay exactly the same?

## Setup

- `shadow_state.hpp`: `ShadowState` with its **own value store**, and `Pair`, the old tracker and the shadow side by side, sharing only
  the stream. It emits nothing.
- `oracle.hpp`: the ground truth by brute force: every way through every `COND_EXEC`, over a sequence of buffers, on real dwords.
  What cannot be followed may leave anything.
- `shadow_test.cpp`: Catch2, built with the real `full_state.cpp` (`CMakeLists.txt`, its own project).

**The contract.** A register reported Certain holds that value at every end of the stream, under both readings of a count past a
buffer's end, in the host's view of packets and tables. Anything else is Uncertain or Absent.

**The boundary contract (Codex's second finding).** What the CP does when a `COND_EXEC` count runs past the end of its buffer has
no source here (TODO(verify)). So the oracle checks both readings, stopping at the end and carrying on, and the shadow must be right
under both. It carries the rest of the count as conditional, so a write there is Uncertain. A count ending inside a packet means the
skipping way decodes other dwords: everything is Uncertain and the rest of the buffer conditional.

## Result

Laptop, MSVC C++20 `/W4 /WX`, Debug: `cmake -S . -B <build>`, `cmake --build <build> --config Debug --target shadow0384`,
`shadow0384.exe`, rc 0: 7 test cases, 68,766 assertions (`raw/run.txt`). clang-cl with the strict warning set: see `raw/clang-cl.txt`.

| Check | Result |
|---|---|
| Codex's case 1: target 0x22, dead tail 0x33 | old 0x33, shadow Certain 0x22, old `emit_prefix` unchanged |
| Codex's case 2: `[set 0x11, cond]` then `[set 0x22]` | Uncertain. The oracle gives 0x22 if a count stops at the end, and 0x11 or 0x22 if it carries. With the carry taken out, the same false 0x22 returns |
| Oracle against shadow | 340,000 random streams, 4 seeds: **0 unsound**, 0 too big to check; 27,949 certain registers in the first 40,000, so it does not pass by claiming nothing |
| Mutants, each caught | CHAIN as a call 580 of 6,000; no carry 763; conditional writes as plain 2,086; what cannot be followed only counted 1,870; a conditional CHAIN's tail as plain 38; a count inside a packet ignored 494 |
| Old bytes | 40,000 random streams, 24,368 with a CHAIN: `emit_prefix` of the old tracker in the pair equals a tracker alone |
| The defect, seen through the pair | the old value differs from a certain shadow value on 1,257 registers of those streams |
| Plain streams | shadow and old tracker agree exactly |

**The oracle earned its keep.** The first version was unsound in 126 of 40,000 streams, with all mutants caught. Two bugs of mine, both
now named regressions: different ways leave a buffer with different counts, so the carry must be a set, not the largest; and a count
left by a CHAIN's target runs on after the buffer, not in the tail. Neither was unsettled semantics, so the stop rule did not apply.

## Limits

- **The oracle and the shadow share an author and a reading of the packets**, and both follow `full_state.cpp`'s opcodes. Passing shows
  they agree on the contract, not that either matches the CP. No GPU was involved.
- Synthetic streams: three SH registers in the random check, small buffers, one table form. Context, uconfig and config spaces, and
  `CLEAR_STATE`, have named cases only.
- A `COND_EXEC` count's dword semantics follow how the host reads it. Past the end of a buffer it is unsourced, hence both readings.
  Inside a nested target, the count's return into the caller is modelled the same way and equally unsourced.
- **Not modelled:** `SET_BASE`, `INDEX_BASE`, `INDEX_BUFFER_SIZE`, `INDEX_TYPE`, `NUM_INSTANCES`, `CONTEXT_CONTROL` (counted);
  `INDIRECT_BUFFER_CONST` 0x33; the longer conditional IB (Uncertain); a CP stack depth; the GPU writing a table after the CPU read it.
- Both-ends-agree after a conditional reads Uncertain unless the value was already certain: safe, but not exact.
- **Certain is not an emission policy.** Leaving out uncertain registers does not guarantee "no worse than restore off": a program
  pointer and its resources could end up half logical, half ring state. Groups of dependent registers are a separate question.
- The shadow uses `std::map` and is not fast; speed in the host is unmeasured. No real title stream has been through it.

## Verdict

The contract holds in C++ on synthetic streams, Codex's two cases are closed, and the old bytes are unchanged, CHAIN streams included.
That supports the design. It does not change runtime, and no runtime decision follows from it. Findings F762 (the shadow and its
contract) and F763 (the carry is a set of counts, and a CHAIN's count leaves the buffer) are recorded here. HANDOFF rows wait for
integration, so this commit stays inside this directory.

## Open, not done here

The box scanner, a run of the shadow on real recorded streams, emission groups, and any change to the backend's tracker. Each needs its
own review. Rollback: revert this one commit.
