# 0169 — The slow frames of gameplay: the direct mapper rebuilt its ~17,000 GPU mappings against every zero piece at each layout change; now only the new mappings are handled

**Question.** After F221/F222 the maintainer still saw the picture slow down and speed up in
gameplay (sessions 13:54 and 14:52; the F208 session measured it in exp 0160: the slow frames
spend ~34 ms of host memory sync on the game thread). Where does that sync go?

**Setup.**
- `route.sh <run> "<env>"` (new, here): one scripted gameplay run (start, slot 1, Continue; the
  save loads at +121 s; killed at +230 s) with extra environment, then `stallcmp.sh` (exp 0167).
- `KYTY_BC5_MAP_STATS=1` (new, `memory.cpp`, `libAmpr.cpp`): once a second, the AMM map and unmap
  commands and the GPU-side unmaps (the synchronous round trip to the GPU thread) with their time.
- The direct sync's journal line (`timing split over 128 submissions`) now splits a full sync into
  scan (chunks to import), merge, drain (the GPU wait before the mappings change, and how many),
  maps (the mapping rebuild) = want + drop + zero + add.
- Runs 815–816 (map stats), 817 (phase split), 818 (the fix); all on the 15:0x box tree, chains
  off, the gameplay window t 130–230 s.

**Result.**
- Map costs (815–816): the GPU-side unmaps are cheap (≈15 µs each, at most 59 ms in a second);
  the AMM maps cost the game thread 0.1–0.15 ms each while loading and 0.4–0.55 ms in gameplay,
  10–17 ms a second on average (worst second 140–180 ms). Not the main cost.
- Host sync (816): 11.1 s of 100 s of gameplay in the direct sync, concentrated in 328 frames
  (12 %) averaging 78 ms.
- Phase split (817): of 6.0 s of direct sync, the GPU drain was 8 ms in 169 drains; the mapping
  rebuild 4.5 s — 169 rebuilds of ~26 ms, each for a handful of changed mappings
  (`maps +1 -0` … `+25`). The rebuild released the zero pieces (exp 0156's scratch, F208's zero
  window) against **every** wanted mapping (~17,000, each a linear scan of the pieces) and
  inserted each new mapping into a sorted vector.
- Fix (`bc5LleAgc.cpp`, step 2 of `direct_sync_one`): zero pieces are released only for the
  mappings about to be added (a piece never lies under a kept mapping: `scratch_fill` fills holes
  between mappings), and the new mappings are merged into the kept list in one pass.
- Run 817 → 818 (same route, same build otherwise): mapping rebuild 4,497 → 295 ms (want 101,
  drop 152, add 29); direct sync 6.0 → 2.0 s; frames over 70 ms 72 → 6; over 40 ms 272 → 247;
  mean frame 31.2 → 30.6 ms; no frame over 250 ms; audio clean. The remaining frames over 40 ms
  (mean 48 ms) split evenly: 22 ms in the host (sync 8.9, prepare 5.1, CS 5.1) and 24 ms in the
  title.

**Verdict.** The slow frames of gameplay were the direct mapper's mapping rebuild, quadratic in
the zero pieces; it now touches only what changed (F223). The long frames (over 70 ms) are gone
from the measured window; the rest of the frame time is the title's own and the per-submission
cost of exp 0162 (chains, ADR 0010, still off by default).
