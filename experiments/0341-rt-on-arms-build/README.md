# 0341 — the RT-on arms 1, 2 and 4 of exp 0340 in one private build, each behind its own switch

**Question.** Exp 0340 (F413) named the two RT-on machine-down classes left on one ring: a runaway
`DISPATCH_INDIRECT` whose argument triple passes the CP check's per-dimension limits (F403, devcd1 of 10-27: 818 ×
820 × 819 groups, then a TCP read fault), and a stray store over a sync label the CP waits on (F360/F406, devcd8).
Its design's arms 1, 2 and 4 are built here, offline, in the backend alone (the emulator's objects stay the shared
normal build's 9382b1e9; only `libbc5_backend.a` changes), each default off behind a switch, so that the test can
turn them on one at a time: does the private build pass the backend's unit tests, build, and run the RT-off S6N route
600 s on one ring with all three on — and then, on the maintainer's yes, his RT-on play?

**Setup — the backend (`backend/`, GPL-2.0, on this branch).**

| arm | switch (environment, read by `Device::open` until the host's option parsing carries it; the `FilterOptions` / `OpenOptions` fields exist) | what it does |
|---|---|---|
| 1 | `BC5_DIRECT_GPU_CHECK_PRODUCT=1` (or `x_limit[:yz_min]`, default 65536:1); needs the CP check (`BC5_DIRECT_GPU_CHECK`) | `indirect_check::ProductLimit`: after the three per-dimension `COND_WRITE`s, a second flag word is set when y > yz_min or z > yz_min (two `COND_WRITE`s), confirmed and synced to the PFP, and a `COND_EXEC` on it runs one more `COND_WRITE`, x > x_limit → the dispatch's flag 0. The CP cannot multiply; the staircase refuses every grid that is not one-dimensional and has more than 2^16 groups along x (F403's triples), and passes a 1-D builder of 2^20. 44 dwords more per checked dispatch, two `PFP_SYNC_ME`s instead of one. GFX form only. `FilterStats::product_checks`. |
| 1 | `BC5_DIRECT_ARGS_HISTOGRAM=1` | `Device::submit` reads the three counts of every GFX-form `DISPATCH_INDIRECT` with a known base at filter time (through `mapped`; stale for arguments the GPU writes later — a histogram, not a verdict), bins them by log2 class, and prints on stderr every 500,000 dispatches and at close: the classes, how many the staircase would refuse, how many the per-dimension limits would. `FilterStats::args_sampled`. |
| 2 | `BC5_DIRECT_SHADOW_LABELS=1` | `bc5/shadow_labels.hpp` (new unit): on the main IB of a GFX-ring job, every label the IB both writes (`RELEASE_MEM` with a value, `WRITE_DATA` to memory) and waits on (`WAIT_REG_MEM[64]`, memory space, after a writer) gets an 8-byte slot in the job's scratch after the flag area (64 slots a job, zeroed per job); each writer is followed by a copy writing the slot, each such wait polls the slot. The title's label is still written (its CPU polls it). The IB's own `COND_EXEC` counts grow around the copies (`insert_before`, which now also appends at the IB's end); an IB whose count would overflow is left alone and counted. `FilterStats::shadow_labels / shadow_writes / shadow_waits / shadow_overflow / shadow_failed`; a summary line at close. |
| 4 | `BC5_DIRECT_BO_JOURNAL=1` | `OpenOptions::bo_journal`: one stderr line (`bc5-direct: bo <what> va 0x… size 0x…`) for every mapping made or undone — userptr (and ro), shared (with id and offset), alias — and the device's own BOs (scratch slots, the snapshot ring, the code area), so a fault address (0xd5200001000, 0xa8256950000, 0xb20407c00000) can be placed. |

The backend prints its switch line once at open (`bc5-direct: experiment 0341 switches: …`). Unit tests (Catch2):
`tests/indirect_check_test.cpp` + the staircase's packet sequence, sizes and refs, a draw and the plain path
unchanged, an insert at the IB's end; `tests/shadow_labels_test.cpp` (new): a label written twice and waited on
(the copies, the redirected wait, `patch`), waits before their writer and register polls untouched, a second
label's slot, the slot limit, an IB without waits, the `COND_EXEC` growth. The host (bc5LleAgc.cpp) is untouched:
the switches reach the backend through the environment.

**Run.** `build0341.sh` on the box (the worktree's `backend/` copied beside it): a private archive and the tests
from `~/bc5-work/exp0341/backend` (cmake, clang, Release, `BC5_WITH_AMDGPU=ON`, `BC5_BUILD_TESTS=ON`, Catch2 from an
earlier test build's cache), the tests run, then the shared normal build's link command (ninja compdb) with the
private archive in place of `~/bc5-work/backend-ubuntu/libbc5_backend.a` → `~/bc5-work/exp0341/kyty_emulator`;
nothing shared is written. Then `s6n0341.sh <live saves> R1 600` (exp 0339's chain: RT off, one ring, the private
wd, the live saves compared only; `BC5_0341_SWITCHES` all four by default, checked in the emulator's environ):
pass = 600 s, no crash / kernel / TIMEOUT line, flips against 0339's 36.9–38.6/s, the histogram's classes and its
"would refuse" counts (expected 0 with RT off), the shadow summary (labels per job, nothing left alone), the bo
lines. The RT-on test is the maintainer's play on a test shortcut with the switches, after his yes.

**Result (2026-10-27, 08:49–09:08; GO: build, then one RT-off run).**
- *Build.* Four attempts on the box, all under -Werror with 0 warnings: (1) one test expectation of my own wrong —
  the shadow copy now goes right before its writer, inside the same `COND_EXEC` range, so a skipped writer skips its
  copy too (the copy after the range would have run unconditionally); (2) 60 test cases, 32,340 assertions passed,
  the emulator relinked (4fc189ad) — and the title crashed at 5 s (`runtimeLinker.cpp:1165`, a null read, `raw/R1-*`):
  the new fields in `FilterOptions` / `FilterStats` / `OpenOptions` had changed the structs the host's objects were
  compiled against; (3) the switches and their counts moved into the backend's `Device` (the headers now differ from
  main by comments only), archive 1a…/emulator **a1976905**; (4) a periodic shadow summary (a killed emulator never
  reaches the close summary), emulator **b052d860** = the tested binary. `raw/backend-tests.out`, `raw/binaries.txt`.
- *R2, the regression run* (a1976905; S6N, RT off, one ring, all four switches on, 600 s): **pass** — 0 crash /
  kernel / TIMEOUT lines, fdinfo `drm-engine-gfx` only, 0 `compute ring:` lines, the live saves 88374d489b09ac70
  unchanged; **36.6 flips/s** (median 387 per 10 s) against exp 0339's 36.9 and 38.6 on the same chain without the
  arms: within the run-to-run spread, at its lower end (two `PFP_SYNC_ME`s per checked dispatch, a `RELEASE_MEM` per
  sync more). `raw/R2-*`.
- *R3, 120 s on b052d860:* pass; the shadow summary every 2000 shadowed jobs (`raw/R3-0341-lines.txt`): **in 18,000
  jobs 127,606 labels, 255,212 writes copied, 127,606 waits redirected** — about 7 labels a job, each written twice
  (the `WRITE_DATA` 0 and the `RELEASE_MEM` 1 of F360's triple) and waited on once, exactly the shape the guard was
  built for; **16 labels without a slot** (one job in a thousand holds more than 64) and **0 IBs left alone**; the
  product staircase on 124,272 dispatches in 120 s.
- *The argument histogram* (`raw/R2-0341.txt`, 1,000,017 triples read at filter time in R2's first ~5 min): the
  legitimate classes are one-dimensional — x of 2^6…2^15 with y = z = 1 — and the stale reads show as `0.1.1`
  (205,116) and `2^31.2^31.2^31` (215,391: the host read the arguments before the GPU wrote them, as exp 0050 found);
  the staircase "would refuse" 239,806 of them and the per-dimension limits 267,357 — stale values, not verdicts: the CP
  decides on the final values, and the route ran as before. No class with y > 1 and x > 2^16 exists among the
  non-stale reads, so the staircase costs the RT-off work nothing and would catch F403's 818 × 820 × 819.
- *The bo journal* (R2: 62,491 lines): 37,010 shared maps, 316 scratch slots, the alias maps of the learned windows
  at 0xffff8011ce000000… (the kernel's sign-extended high half), the scratch at 0x100000000000 + 4 GiB per slot; no
  userptr maps on this title (every title mapping is a shared memfd one).

**Verdict.** The three arms build, pass the backend's tests and run the RT-off route on one ring 600 s without a
cost beyond the run-to-run spread: the shadow labels take over every end-of-pipe sync of the title (seven a job), the
staircase is in place on every checked dispatch, the mappings are journaled. The RT-on question — does F403's
runaway grid get refused, does F360's stray store no longer hang the CP — is the maintainer's play on a test
shortcut with the switches (`BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1`, the histogram and the bo
journal as he likes; one ring), after his yes. Follow-ups: 128 shadow slots (one job in a thousand overflows 64);
reading the flag words back after a job to count the CP's actual refusals; the switches into the host's option
parsing at integration (the headers' comments say so).
