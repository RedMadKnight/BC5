# Experiment 0401 series e7, tag `zsk`: exp 0379's zero skip on the e6 unit

**Why.** The maintainer, playing e6: "Ram się dusi". The top session's read at t ≈ 684 s: GTT 12,889 of 13,312 MiB,
MemAvailable 216 MiB, swap 1.4 GiB, PSI memory "full" avg60 23.6 %, 5–16 flips/s. Series d had exp 0379's zero skip
(it pins the all-zero 2 MiB chunks of the two big eager render heaps less: 1.9 GB less GTT on the bench, F541; about
0.35–0.6 GiB in exp 0388's 37-minute play). The e-series (e2–e6) does not have it. `zsk` carries it into e7, behind its
own switch, default off.

**What.** `mkzsk0401.py <root> <out>` edits `src/libs/bc5LleAgc.cpp` of the e7 input tree (e6's final unit, md5
`d1cfd9bb1f1b3485bed4207a7f064d4f`: main's unit + `mkunit0401.py` + e4's `mkfl0401.py` + e5's `mkeq0405.py` and
`mkgpu0405.py`) into `8710207ea5c34ad70e48dfbbff9880fd`. It writes one file, the unit; nothing goes beside it.
The input md5 is pinned in one dict at the top of the script (`INPUTS`), for the top session to re-pin when it chains
`zsk → lzr → cap`.

## Sources

- Exp 0379, `experiments/0379-zero-skip/`: `patch0379-bc5LleAgc.diff` (md5 `6f0c7c16`, 11 hunks on main's unit
  e7cc2f60), `raw/zskip_block.cpp` (the block, byte-identical to the diff's block), README (design, the B1/G2 runs,
  the 0379t plays). The header `backend/include/bc5/zero_skip.hpp` (md5 `782ca0e94aa9ca708a33f185a0c6a42c`, the same
  on main and in this worktree) and its Catch2 test `backend/tests/zero_skip_test.cpp`.
- Exp 0388, `experiments/0388-job-arena-root/memory/README.md`: the moving list `zero-list-moving.txt` (md5
  `843f9fbcde4d9c2d324e8cba78cdbae5`, 1,014 MiB in 40 runs, every recorded canary-hit run left out) and the 37-minute
  play's take-back figures. Series d ran 0388's unit (0379 + 0388's shared canary slices, `BC5_DIRECT_ZERO_SLICES`,
  off unless set; `patch-z-bc5LleAgc.diff` on branch `exp/0388-job-arena-root`). Its launcher set only
  `BC5_DIRECT_ZERO_SKIP` (`shortcut0401.sh` mode `cpacb-d`), so series d played exactly exp 0379's skip. The slices
  are not carried here.

## The hunks (all 11 of exp 0379's diff fit by content; none failed)

Input lines are d1cfd9bb's, output lines 8710207e's. Every edit inserts whole lines only (`diff` shows 748 added, 0
removed). The script asserts each anchor once, in file order, and inside the direct path (`#if defined(KYTY_BC5_DIRECT)`
… `#else static void init_once`), except the include anchor, which it asserts inside the direct path's include block.

| # | exp 0379's hunk | anchor (input line) | inserted (output lines) | how it was carried |
|---|---|---|---|---|
| 1 | `#include "bc5/zero_skip.hpp"`, `<sys/resource.h>`, `<sys/syscall.h>` | after `#include "bc5/full_state.hpp"` (36) | 37–258 | **adapted:** the two system headers as in 0379; the header's lines 13–228 inlined byte for byte (md5 `8355b699…`, 8,876 bytes, asserted by the script) instead of the include, so no include path changes and nothing has to sit beside the unit |
| 2 | the scan and skip block | before `static void direct_sync_one(DState& S, bool force) {` (1982) | 2204–2735 | 0379's block, with the changes listed below, plus the CPU test's seams at its end |
| 3 | placement, scan tick, a hit's full sync, before the fast path | after `const uint64_t sig = views_p->sig;` / `if (sig != S.views_sig) g_layout_gen++;` (2006–2007) | 2762 | **adapted:** the same statements moved into `zskip_sync_start(S, views)`; one call line |
| 4 | `zskip_take_back(S, fd)` and `zskip_on` | after `const uint64_t t_scan0 = SoftCp::now_ns(); // experiment 0169` (2021) | 2777–2778 | as in 0379 |
| 5 | the eager loop skips listed chunks | between the eager `for (uint64_t c = v.off & …` and its `if (direct_covered_end…` (2026–2027) | 2784 | as in 0379 |
| 6 | the forced loop skips them too | between `for (const uint64_t c: S.forced) {` and its `if (direct_covered_end…` (2043–2044) | 2802 | as in 0379 |
| 7 | `zskip_release` before a real mapping | before `if (g_dev->map_shared(w.id, w.bo_off, w.size, w.va)) {` (2191) | 2950 | as in 0379 |
| 8 | `zskip_map` after the rebuild | between `S.maps.swap(next);` and `S.views_sig  = sig;` (2208–2209) | 2969 | as in 0379 |
| 9 | `direct_force`: a hint takes a chunk back | before `if (S.forced.insert(c).second) here += kDChunk;` (2268) | 3029 | **adapted:** 0379 replaced that line with a block; here one line is inserted, `if (zskip_hint_back(S, c) && S.forced.count(c) != 0) here += kDChunk;`, and today's line stays. Together they count the chunk once, as 0379's `insert(c).second \|\| back` did |
| 10 | `map_window`: a learned window leaves chunks skipped | after `static void map_window(…) {` (2601) | 3364 | **adapted:** 0379 replaced the `if (const uint64_t asked = direct_force(lo, hi); …)` line with set, call, reset of `t_force_learned`; here a scope guard `const ZLearned zlearned(std::strcmp(what, "learned") == 0);` is inserted and today's line stays. `map_window` calls `direct_force` only there, so the flag covers the same call |
| 11 | `zskip_disable("device reopen")` | after `g_scratch.clear();` / `g_scratch_id = 0;` in `recover_after_timeout` (6404–6405) | 7169 | **adapted:** indentation only (two tabs here; three in main's unit as 0379 saw it) |

Changes inside the block (a whitespace-blind `diff` against `raw/zskip_block.cpp` shows these and nothing else):

- **`zskip_path`:** `BC5_DIRECT_ZERO_SKIP` is read as every e-series switch (F767, `bc5::env_on`): unset, empty and
  `0` are off. In 0379, `0` was a list path called "0": nothing was placed, but the list read and the minute report
  still ran.
- **`zcanary_check(r)`:** the watcher's loop body, moved into a function of its own (the same statements; the
  `continue` became a `return`). `zcanary_watch` calls it.
- **`zskip_take_back`: a late hit is retired (the one change of behaviour).** Say the canary sees a write on a run that
  hints and CPU writes have already taken back in full (`g_zleft[r] == 0`). In 0379 its flag stayed at 1. The check at
  the start of every sync then forced a full sync at every call (`S.blocks = ~0`, the SEEK_DATA walk over every view),
  for as long as anything stayed skipped. Now the flag goes to 2 (done) and a journal line says so. No hit is counted,
  because nothing was taken back. This can happen when a write lands in the slice through a canary mapping that a hint
  then takes back before the watcher looks. The slice keeps the data, and the watcher flags it on its next round.
- **`zskip_hint_back`, `ZLearned`, `zskip_sync_start`:** 0379's statements from hunks 9, 10 and 3 as functions.
- **`g_zsk_cpu_test`:** false in the emulator. Only `bc5_zsk0401_reset(1)` sets it. When set, `zskip_resolve` takes
  its canary memfd without a BO (id 1), so the CPU test runs the real placement and the real canary thread. The
  emulator's expression is 0379's.
- **The seams `bc5_zsk0401_*`** (13, `extern "C"`) at the end of the block. They are always compiled in and never
  called by the emulator.

**Off = today's e6 path.** With the switch unset, `0` or empty, `zskip_path()` is null. Then `zskip_resolve` returns
at once, the list is never read, and `g_zskip` stays empty. So `zskip_take_back` returns, `zskip_on` is false,
`zskip_hint_back` returns false (today's `forced.insert` line counts as before), `zskip_map` returns at
`g_zskip.empty()`, `g_zpieces` stays empty and `zskip_disable` returns. What is left is a thread-local flag set and
reset in `map_window`, and the scan diagnostic's one-time read of `BC5_DIRECT_ZEROSCAN_AT` in `zscan_tick`, as in
0379.

## Functions touched

- **Existing, lines inserted only:**
  - `direct_sync_one`: 6 places, 7 lines (hunks 3–8);
  - `direct_force`: 1 line;
  - `map_window`: 1 line;
  - `recover_after_timeout`: 1 line;
  - the include block of the direct path.
- **New, all in the block before `direct_sync_one`:**
  - exp 0379's functions: `zero_names`, `zero_heap_span`, `zscan_run`, `zscan_tick`, `zskip_path`, `zcanary_check`,
    `zcanary_watch`, `zskip_release`, `zskip_map`, `zskip_resolve`, `zskip_take_back`, `zskip_report`,
    `zskip_disable`, `zskip_hint_back`, `zskip_sync_start` and `struct ZLearned`;
  - the test helpers `zsk_views` and `zsk_state`, and the seams `bc5_zsk0401_switch`, `_list`, `_mask`, `_all_zero`,
    `_set`, `_place_set`, `_state`, `_reset`, `_sync_start`, `_hint`, `_take_back`, `_pieces` and `_disable`;
  - `namespace bc5::zero_skip` (inlined) at global scope after the includes.

**For lzr and cap.** A chain dry run on the laptop applied cleanly: this output, then `mklzr0401.py` (snapshot
`d7d8e53e`), then `mkcap0401.py` (snapshot `e33befc0`), each re-pinned in a scratch copy only. Every zsk text came
through byte-identical (the header, the block, the 9 call lines).

Two things in that chain need a decision:
- `box0401.sh` copies `*.inc` from the last script's directory only, so lzr's `lzr0401.inc` is lost when cap runs
  after it. zsk writes no .inc.
- lzr reads `BC5_DIRECT_ZERO_SKIP` as "set". zsk reads "set, non-empty and not 0". With `=0`, lzr still protects the
  zero-name heaps, which errs on the safe side.

## Switch, environment and journal

- **`BC5_DIRECT_ZERO_SKIP=<path of a zero list>`**: on. Unset, empty or `0`: off.
  - The value is the path. `=1` would be read as a list named "1": `zero skip: list 1, 0 heaps …` and nothing skipped.
  - It acts only on eager views (`BC5_DIRECT_EAGER_NAMES`, set by the shared launch environment for the two heaps).
- Exp 0379's diagnostics are carried unchanged: `BC5_DIRECT_ZEROSCAN_AT`, `_OUT`, `BC5_DIRECT_ZERO_NAMES` and
  `BC5_DIRECT_ZERO_MIN_MIB` (the scan is `BC5_DIAG_ENV`, so the normal build only). The e7 arms must not set them:
  each scan reads 5.4 GB.
- **What the e7 arms need.** Series d's words, from `shortcut0401.sh` mode `cpacb-d`:
  - `BC5_DIRECT_ZERO_SKIP=$HOME/bc5-work/exp0388/m/zero-list-moving.txt`;
  - before the start, the list checked against md5 `843f9fbcde4d9c2d324e8cba78cdbae5`, stopping if it differs
    (`shortcut0401.sh:81`).
  - The arm without the skip leaves the word unset.
- **Journal lines** (direct.log):
  - at the first sync after the heaps exist: `zero skip: list <path>, 2 heaps, 1014.0 MiB listed, 0 bad lines`;
  - per heap: `zero skip: RenderGpuWcLarge at file 0x…: … MiB in 37 runs skipped` (or `… spans 0x…, the list says
    0x…: not skipped` after a title update);
  - `zero skip: canary BO <id>, 40 slices of 2 MiB`, then `zero skip: canary +N mappings (M)`;
  - every minute: `zero skip: X MiB still skipped of Y placed; taken back: … by CPU writes, … by hints, … runs by
    canary hits; … canary mappings`;
  - at each hit: `zero skip: canary hit in run r (file 0x… +… MiB): … MiB taken back`;
  - new in e7: `… after all of it was taken back: nothing to take`;
  - `zero skip: off (device reopen)`.
- **For `box0401.sh`'s strings check:** `BC5_DIRECT_ZERO_SKIP`, `zero skip: list %s` and `after all of it was taken back`.
- **Gate row:** `"zsk0401.cpp src/libs/bc5LleAgc.cpp BC5_DIRECT_ZERO_SKIP zsk0401"`.
- **Edit row:** `"zsk mkzsk0401.py - src/libs/bc5LleAgc.cpp:d1cfd9bb1f1b3485bed4207a7f064d4f:8710207ea5c34ad70e48dfbbff9880fd"`.

## The CPU test `zsk0401.cpp`

It calls the real unit through the seams. It never calls `Direct::init_once`: no device is opened, `g_dev` stays
empty, and nothing is imported, mapped or submitted. The test's "direct memory" is its own sparse memfd (144 MiB). The
canary is the unit's own memfd, and the unit's own watcher thread watches it.

- **On** (`BC5_DIRECT_ZERO_SKIP` set, any value): the test writes `zsk0401-list.txt` into its fresh working directory
  and points the switch at it before the unit first reads it. 14 cases, **176 checks**:
  - the switch;
  - exp 0379's five Catch2 cases: the round trip, the parser (7 bad lines), the mask, `all_zero`, the skip set;
  - no device: placed, then cleared, and off for the session;
  - placement: heap A placed in 3 runs (28 MiB), heap B refused (span 34 against 32 MiB), 4 slices, the per-run bytes
    left;
  - hint and learned window;
  - CPU write (SEEK_DATA);
  - canary hit: the watcher sees a byte written into run 1's slice, the sync goes full, the run is taken back;
  - hit after a full take-back (e7's change);
  - canary mappings released;
  - device reopen.
- **Off** (`=0` or unset): 9 cases, **77 checks**:
  - the switch reads off;
  - the five pure cases;
  - nothing placed, even with a canary at hand (no list read, no slice, no memfd);
  - hint, CPU write and reopen change nothing;
  - canary mappings released.
- The last line is `zsk0401: on 176 of 176; end` or `zsk0401: off 77 of 77; end`. It exits 0 only after `; end`. A
  60-s watchdog prints a FAIL line, and each canary wait gives up after 10 s.

## Laptop checks (2026-11-04, no box)

- **The script:**
  - applies to the e6 tree (`scratchpad\e7\e6tree`) and prints `src/libs/bc5LleAgc.cpp 8710207ea5c34ad70e48dfbbff9880fd`;
  - refuses its own output (`BC5_DIRECT_ZERO_SKIP is in it`), a changed input (md5 `157c5c38…` against the pin) and an
    out dir equal to the root;
  - leaves the input unchanged (still d1cfd9bb).
- **Undo:**
  - the script's in-memory revert gives the input back;
  - so does `patch -R` of `diff -u input output` on a copy of the output (d1cfd9bb again).
- **Braces:** per edit (comments and literals stripped, since comments write intervals as `[lo, hi)`) all three kinds
  balance. Over the whole file, braces are 2007/2007 in the input and 2154/2154 in the output.
- **Syntax:** Visual Studio's clang++ 22 (msvc target), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`.
  - The whole unit, input against output, with `-ferror-limit=0`:
    - The stand-ins: the batch-1/2 stubs (`lib0405chk\stub`, `e5\gpucheck\ustub`, fmt, magic_enum) plus
      `scratchpad\zsk\whole\stub`. The extra stub declares the Linux names MSVC lacks (memfd, pread/pwrite, SEEK_DATA,
      mincore, setpriority, syscall, …) and maps `st_blocks` so that `direct_sync_one` is checked to its end.
    - With `KYTY_BC5_DIRECT` and `backend/include`: 3 errors in both, the same messages.
    - Without it: 6 in both, the same messages.
    - All of these are in today's code or the stub: MSVC's `stat`, the two `-Wmissing-field-initializers`, and
      `mmap` without the direct path.
  - The block and the inlined header in a stand-in harness (`scratchpad\zsk\run\harness.cpp`, plus `-Wshadow
    -Wformat=2`): clean.
  - `zsk0401.cpp`: clean.
- **Stand-in run** (`scratchpad\zsk\run\build.sh`):
  - It links the test with the extracted block, the header and the unit's own `DView`/`DState`, a fake memfd shim
    (sparse pages, SEEK_DATA) and lld.
  - Results: on `176 of 176; end`, `=0` `77 of 77; end`, unset `77 of 77; end`. All exit 0. Each ran in a fresh
    directory and left only the on-run's list.
- **Negative controls:** five mutants of the block, each caught:
  - 0379's take-back line, without the late-hit retire: on 174 of 176;
  - 0379's `getenv`-only switch: `=0` 73 of 77;
  - a learned window that takes chunks back: on 171 of 176;
  - a watcher that never sees a write: on 161 of 176;
  - no CPU-write walk: on 167 of 176.

## Risks

- **A canary hit loses the GPU's write until the watcher sees it.** With 40 slices at 50 ms, that is up to 2 s, and it
  may show as a one-frame glitch (F542). Exp 0388's play saw 11 hits in 37 minutes on the 1.2 GB list. The moving list
  leaves out all 13 recorded hit runs.
- **A device reopen imports every skipped chunk at once**, about 0.9 GB more pinned at the worst moment (0379's design).
- **A chunk a hint forced before its heap was placed is still placed.** `zskip_resolve` does not look at `S.forced`,
  which mixes hint and learned chunks. It is 0379's behaviour, and the canary covers it.
- **TODO(verify):** whether the CPU sees the GPU's writes to an imported udmabuf page without a flush (0379's
  `clflush` comment).
- **The gain is smaller than the pressure.** The play figure is about 0.35–0.6 GiB (0388), against e6's 216 MiB
  MemAvailable at 12.9 GB GTT. It helps; it does not cure the pressure alone.
- **The late-hit retire has not run on the box.** It only changes what happens after such a hit.
- **The seams are test code in the production unit.** They are inert unless called.

## Not checked

- The box's Linux compile with the shared compdb command, and the link with every emulator object.
- The gate run on the box, with a real memfd's SEEK_DATA on shmem and `clflush` on a memfd mapping.
- Anything that needs the GPU: the canary BO import, `zskip_map`'s mappings, and `zskip_release` with a device.
- The play.
- lzr's and cap's final scripts. The chain was dry-run on their snapshots only.

## Files

| file | md5 |
|---|---|
| `mkzsk0401.py` | `571c04b58a269b64069c46f9ebf99a8c` |
| `zsk0401.cpp` | `bafb6938523acb784d45fd70768e2c25` |
| input `src/libs/bc5LleAgc.cpp` | `d1cfd9bb1f1b3485bed4207a7f064d4f` |
| output `src/libs/bc5LleAgc.cpp` | `8710207ea5c34ad70e48dfbbff9880fd` |
| inlined `backend/include/bc5/zero_skip.hpp` (whole file / lines 13–228) | `782ca0e94aa9ca708a33f185a0c6a42c` / `8355b699a5443434a23b607e3df1b397` |
| e7 arms' list `~/bc5-work/exp0388/m/zero-list-moving.txt` (= `0388-job-arena-root/memory/zero-list-moving.txt`) | `843f9fbcde4d9c2d324e8cba78cdbae5` |
