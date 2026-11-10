# zcb: the zero skip's fixes and catchers (exp 0401 series e9)

**Why.** `hang1954-0401.md`, sections "Deep analysis 2026-11-05 (after e8)" and "Box reads after the analysis":
- Both e8 F403 hangs came 0.05–0.11 s after a canary take-back of run 37 (file 0x22da00000, 46 MiB,
  CommitIABufferAllocator, a GPU-written heap).
- The 16 clean arms only ever took back run 23 (file 0x1bc400000, 12 MiB), at t ≈ 315–335 s, without harm.
- `zskip_map` maps every chunk of a skipped run onto the same 2 MiB canary slice (`run * kDChunk + (lo - c)`). The GPU's
  writes alias across the run's chunks.
- `zskip_take_back` then erases the run, and the real chunks get mapped with no copy. Between two frames the GPU's view
  of that memory changes from the aliased canary data to the file's zeros.
- The hole scratch BO (`scratch_fill`) is one read-write 2 MiB mapping over every hole. Its comment ("its writes go
  nowhere") is wrong, and nobody has looked at whether the GPU writes there.

zcb puts two fixes and two catchers into one build, each behind its own switch, default off (CLAUDE.md, "fixes and
catchers first").

**The switches.** Unset, empty, `0` or `off` turn a switch off; that is e8's path, and its switch line is all it adds.
`1` or `on` turns COPYBACK, PROBE or SCRATCH_WATCH on. Anything else is off, and the switch line says it does not
parse. Each switch is read once, at the first direct sync (`zskip_resolve`), and journaled with one line each:
`exp 0401 e9 (zcb): BC5_DIRECT_… on: …` or `… off`.

| Switch | Kind | What it changes |
|---|---|---|
| `BC5_DIRECT_ZERO_SKIP_EXCLUDE=<hex>[,<hex>…]` | fix | A run of the zero list whose file offset is listed is placed as normal memory, not skipped |
| `BC5_DIRECT_ZERO_SKIP_COPYBACK=1` | fix | At a canary hit, the run's slice goes into each of its chunks still skipped, after a bounded wait for the jobs in flight |
| `BC5_DIRECT_ZERO_SKIP_PROBE=1` | catcher (CPU, lines only) | Each take-back journaled; at a fence timeout the last 4 and what the stuck job's own records touch |
| `BC5_DIRECT_SCRATCH_WATCH=1` | catcher (CPU) | A thread scans the hole scratch BO every 50 ms |

**What each does.**
- *EXCLUDE.*
  - Up to 16 file offsets, hex, `0x` optional, as the journal prints them (`zero skip: canary hit in run 37 (file
    0x22da00000 …`). For e9: `BC5_DIRECT_ZERO_SKIP_EXCLUDE=0x22da00000`.
  - An entry must be 2 MiB aligned (a run starts on a chunk). An empty, non-hex, longer than 16 digits, unaligned or
    repeated entry, and one past the 16th, is bad: the switch line names it, and it is ignored.
  - `zskip_resolve` places `zcb_exclude(h, base)`, the heap without the listed runs. One line per run left out:
    `zero skip exclude (exp 0401 e9 zcb): <heap>: the run at file 0x… +… MiB is not skipped: it is placed as normal
    memory`. The chunks then take e8's eager import, as any chunk not on the list.
  - Once every heap of the list is placed or refused, an entry that is the start of no run gets one line
    (`… 0x… is the start of no run of the list's placed heaps: nothing left out for it`). A typo cannot pass for a
    clean arm.
  - Run numbers after a left-out run shift down by one (the skip numbers runs in placement order). Compare runs by
    file offset. The canary keeps one slice per run of the list, left-out runs included.
- *COPYBACK.*
  - In `zskip_take_back`, at a canary hit, before `erase_run`: the run's chunks still skipped are collected. Chunks
    that CPU writes or hints took back before are real memory already and are left alone.
  - The wait: `Device::wait_idle(500 ms)`. It waits for the job queued last on each ring, and a ring runs its jobs in
    order (`backend/include/bc5/direct.hpp`). It queries each ring's fence with the bound in turn
    (`backend/src/direct.cpp`, `Device::wait_idle`), so the total can exceed 500 ms when several rings are busy. It is
    a fence query: it does not wait for the completion threads. `direct_sync_one` already calls it the same way
    (`wait_jobs`) before mappings change.
  - The thread: `zskip_take_back` runs in `direct_sync_one`, on the submitting thread, under `g_dev_mutex`. Every
    submission is made under that lock (`submit_now`), so no new job starts between the wait and the remap.
  - The copy: the slice is flushed (`clflush`, as `zcanary_check` does). Then its non-zero 4 KiB pages are written
    with `pwrite` on the direct-memory memfd (`dstate_fd`, the fd `zskip_take_back` already walks with SEEK_DATA) into
    each chunk still skipped. Nothing goes through the guest's mapping, so aliases need no care.
  - A chunk in which SEEK_DATA finds data was written by the CPU since the last walk. It keeps its data and is only
    counted. In a chunk the file read as zeros, the non-zero pages make it equal to the slice byte for byte.
  - The same `direct_sync_one` then imports the chunks and maps them in place of the canary (e8's code, unchanged).
    The GPU's view stays what it was; the CPU now sees the GPU's writes there, as it would on the console.
  - One line: `zero skip copy-back (exp 0401 e9 zcb): t … s: run r (file 0x… +… MiB): waited … ms (at most 500 ms a
    ring) for the jobs in flight: every ring idle | NOT idle within the bound …; the slice has N non-zero pages of 4
    KiB; B bytes copied into C of the K chunks still skipped, D of them held CPU data …, F writes failed; T chunks
    taken back before stay as they are`.
- *PROBE.*
  - At each take-back by a canary hit, and for each run a CPU-write walk takes chunks from, one line:
    `zero skip probe (exp 0401 e9 zcb): t … s: take-back by a canary hit | CPU writes: run r, file 0x…-0x… (+… MiB), …;
    … canary VAs: …; its slice: N non-zero bytes, first at 0x…, last at 0x…, hash 0x…; jobs in flight: …`.
  - The VAs are the run's canary mappings from `g_zpieces`, adjacent pieces merged, at most 8 ranges named.
  - The hash is FNV-1a's step over 8-byte little-endian words, `h = (h ^ w) * 0x100000001b3` from
    `0xcbf29ce484222325`, the last word zero-padded.
  - *Jobs in flight: a deviation from the brief.* The jobs themselves live in exp 0024's completion queues (`g_cqs`,
    `PendingJob`). Those are defined after exp 0404's block, where zcb may add only the two timeout lines, so the
    take-back line cannot list them. It gives the submissions so far (`g_submits`, the last number) and whether every
    ring was idle at that moment (`Device::wait_idle(0)`, a zero-time query).
  - Each take-back is kept (the last 64), with the skip by run (bytes left, flag, canary VAs). The skip by run is
    taken again after each `zskip_map` pass that added mappings and at the end of each `zskip_take_back` that took
    something back. Both sit under a mutex of zcb's own; the completion thread reads them at a timeout.
  - At a fence timeout, a header line, the last 4 take-backs (age in s, kind, run, file range, VAs), then the job's
    line. The job's addresses are its buffer and, from the host's copy of what it ran, each packet's memory operands
    (`bc5::policy::memory_operands`: SET_BASE, INDEX_BASE, label waits and writes, DMA_DATA, …) and the
    COMPUTE_USER_DATA pairs in force at each dispatch, read as 48-bit addresses (sh 0x240–0x24f, as `timeout_probe`
    reads them). The line names each address that falls in a taken-back run or in a still-skipped run.
  - The host's copy is `sub_ib` in `submit_now`'s sync path. In the completion thread it is the job's `ib_copy`, kept
    only with `BC5_DIRECT_TIMEOUT_PROBE`; without it the line says so and uses the buffer's own range.
  - "Touch" means an address of the job's records lies in the range. It is no proof that the GPU used it (LESSONS R13,
    R21). V#s and tables in memory are not read.
  - Hint take-backs (`zskip_hint_back`) are not probed: that function is not one zcb may change.
- *SCRATCH_WATCH.*
  - `scratch_bo` never maps the scratch memfd on the CPU. Right after its import, `zcb_scratch_watch_start` maps it
    read-only (`mmap`, `PROT_READ`, `MAP_SHARED`) once a session and starts a thread at nice 19.
  - Every 50 ms the thread flushes the 2 MiB and checks them with `all_zero`, as `zcanary_watch` does.
  - The first non-zero scan is journaled at once (`scratch watch (exp 0401 e9 zcb): t … s: the hole scratch BO is not
    all zero: N non-zero bytes, first at 0x…, last at 0x…, hash 0x…`).
  - After that, a change is journaled at most once per 10 s, up to 64 lines. A change in the gap waits, and the scan
    that ends the gap gives the state then.
  - The memfd outlives a device reopen (`recover_after_timeout` resets only `g_scratch_id`), so the mapping stays
    valid.
- *At a fence timeout.* One line before each of exp 0404's two `fl_probe` lines calls `zcb_at_timeout` (the completion
  thread and `submit_now`'s sync path). With PROBE: its lines. With SCRATCH_WATCH: one line from a fresh scan, `the
  hole scratch BO is DIRTY: …` or `… is clean …`, or `… is not watched` before the BO exists.
- *The quiet filter.* Every line starts with `exp 0401 e9 (zcb)`, `zero skip … (exp 0401 e9 zcb)` or `scratch watch
  (exp 0401 e9 zcb)`. `journal_quiet_kind` drops only its six per-event kinds, and none of these is one, so
  `BC5_DIRECT_JOURNAL_QUIET=1` keeps them all. The lines written at a timeout say "at the timeout" (kind -1): the
  quiet ring is written out before the first one, as before exp 0404's crumbs.

**The edit** (`mkzcb0401.py`, on e8's unit bd181169 → 2fcf42d2, every anchor once, balance kept, undo checked):
- In exp 0379's zero-skip block:
  - a block of declarations before `zskip_release`. zcb's functions are called from `zskip_map`, `zskip_resolve` and
    `zskip_take_back`, which come before the block's end line. *A deviation from the brief*: declarations only, the
    code is before the end line;
  - `zskip_map`: one line, the snapshot after a pass;
  - `zskip_resolve`: one line (the switch lines), the exclusion (one line added, `place(h` → `place(hz`, and the
    journal line's run count from `hz`), one line (the unmatched entries);
  - `zskip_take_back`: one line at a canary hit (`zcb_hit`), three in the CPU-write walk, one at its end;
  - the host block and the seams `bc5_zcb0401_*` before the end line.
- In the scratch BO's creation: two comment lines correcting "its writes go nowhere", and one call in `scratch_bo`.
- One line before each of exp 0404's two `fl_probe` lines.
- The script asserts that nothing else changed: the unit before the zero-skip block; between it and the scratch BO;
  and between the scratch BO and exp 0404's block (the given-up waits' code, `learned_load` and `learned_apply` are
  there). From exp 0404's block on, only the two lines are added (`learned_apply`'s call site is there too).
- The script's balance check now skips C++14 digit separators (`2'000'000'000ull`). mksmp0401.py's stripper read
  them as character literals, which left e8's whole unit at (21, 15, 2) instead of (0, 0, 0).

**Costs.**
- *EXCLUDE.* The listed runs are imported: 46 MiB more pinned for run 37. The e6/e7 plays had little memory to spare
  (`zsk0401-notes.md`).
- *COPYBACK.*
  - At a canary hit (about once an arm), a wait of up to 500 ms a ring on the submitting thread, under `g_dev_mutex`:
    a hitch instead of an unmet view.
  - The copy writes only the slice's non-zero pages: small when the GPU wrote little.
- *PROBE.* A line per take-back and a 2 MiB summary of the slice; a zero-time fence query; a walk of `g_zpieces` per
  snapshot. At a timeout, a few ms before exp 0404's crumbs, for the operand walk.
- *SCRATCH_WATCH.* One 2 MiB flush and `all_zero` per 50 ms on a nice-19 thread, like the canary watcher's one slice per
  50 ms. When the BO is dirty, also the 2 MiB summary each scan.
- *Off.* The switch lines, a static flag test per sync, an empty vector per run in the CPU-write walk, and a call that
  returns at a timeout.

**Risks.**
- *COPYBACK keeps the aliasing while a run is skipped.* Two chunks of a run share one slice, so a GPU write to one shows
  in the other. The copy makes memory after the take-back equal what the GPU saw then, which is not what the console
  would hold. EXCLUDE removes both for the listed runs. A slice per chunk (the analysis's `ZERO_SKIP_PER_CHUNK`) is not
  built here.
- *The wait's bound.* When a ring is not idle within it, the GPU may still write into the slice after the copy; the
  line says so.
- *A guest store into a still-skipped chunk between SEEK_DATA and `pwrite`* would leave the chunk mixed. The window is
  short and needs the CPU and the GPU to write the same 2 MiB at once.
- *The CPU now sees the GPU's writes in those chunks.* In e8 it never did; on the console it would.
- *Coherence.* TODO(verify), as exp 0379's `zcanary_check` says: whether the CPU sees the GPU's writes to an imported
  memfd page without a flush. The slice is flushed before every read. The other way, the GPU reading pages the CPU
  wrote through the memfd, is how every CPU write of the title reaches the GPU on this path (ADR 0006).
- *`pwrite` on the direct-memory memfd.* memfd_create(2) opens it read-write; F_SEAL_SHRINK (`bc5/direct.hpp`, ADR
  0006) does not forbid writes (fcntl(2): only F_SEAL_WRITE does). TODO(verify) on the box: the copy line's "writes
  failed" count shows it.
- *PROBE's jobs in flight* are a count and an idle bit, not the jobs (see above).
- *The seams and the test hooks* (`g_zcb_test_wait`, the line capture) are test code in the production unit. They are
  inert unless the CPU test calls them.
- *The watch thread has no stop.* It reads a read-only mapping of a memfd that lives for the session.

**Checks (laptop, 2026-11-05).**
- *The script*
  - `"/c/Program Files/Python314/python" -I mkzcb0401.py <scratch smp/out> <scratch e9/zcb/out>` gives
    `src/libs/bc5LleAgc.cpp 2fcf42d2d7528e269d821444ee4fbe9e` (input bd1811690b685369194602027b61a2d5).
  - It refuses its own output ("the unit has the edit already"), e7's unit b010db09 and a copy with one byte changed
    ("not the pinned input"), and an out dir equal to the tree. The input is unchanged.
  - Undo: the in-memory undo gives the input back. So does `patch -R` of `diff -u input output` on a copy of the
    output (bd181169 again). The diff has 819 lines in and 2 out (the two changed lines of `zskip_resolve`). The new
    text is ASCII, LF only.
- *The whole unit* (clang++ 22.1.3, msvc target, `-fsyntax-only -ferror-limit=0 -std=c++20 -Wall -Wextra -Werror`,
  zsk's whole-unit stubs):
  - input and output give the same messages, with `KYTY_BC5_DIRECT` (3 errors) and without (6). They come from the
    stubs and MSVC's headers, as in zsk's check.
  - A negative control (4 call lines broken in a copy: the hit, the scratch call, both timeout lines) adds exactly 4
    errors, so the real call sites are type-checked.
- *The stand-in* (`scratchpad\e9\zcb\mkstandin_zcb.py`): the output unit's real text of the zero-skip block, the scratch
  BO's code, the quiet filter, DView..DState, the inlined zero_skip.hpp and the two timeout lines (in stubs), plus
  `backend/src/policy.cpp`'s `memory_operands`. Stubs for the rest; zsk's fake memfd shim (sparse pages, SEEK_DATA).
  - `-std=c++20 -Wall -Wextra -Werror -Wshadow -Wformat=2`: clean. `zcb0401.cpp` with `-Wshadow`: clean.
  - `zcb0401 on` 221 of 221, `off` 164 of 164, `unset` 164 of 164 (rc 0). With no argument it prints usage, rc 2.
- *zsk's and smp's tests on the output:*
  - `zsk0401.cpp` linked with zcb's stand-in (it holds zsk's seams): on 176 of 176, `=0` 77 of 77, unset 77 of 77, as
    zsk's notes have them. With zcb's switches on as well: 176 of 176.
  - smp's stand-in (`scratchpad\smp\mkstandin_smp.py`) made from the output is byte-identical to the one from the
    input. `smp0401` on 61 of 61, off 61 of 61, no argument rc 2.
  - The box's gates (the unit's compile command, linked with every emulator object) were not run: no box access.
- *Not run: GCC on Linux.* The laptop has no Linux toolchain. On Linux `uint64_t` is `unsigned long`, so every
  `PRIu64`/`PRIx64` argument was read by hand; two (`kZcbWaitNs / 1000000ull`, `4ull * num_dwords`) were
  `unsigned long long` and now carry a cast. The box's compile is the check.
- *Mutants* (`scratchpad\e9\zcb\mutate.py`): 20 mutants of the stand-in, each built and run `on` and `off` in fresh
  directories; all 20 caught (10 of them in `on` only, as their code runs only with the switches on):
  - EXCLUDE: ignored; matched on the heap offset, not the file offset; an unaligned entry accepted; `off` read as on;
  - COPYBACK's switch not read (a misspelt name);
  - the copy: into chunks already taken back; over the CPU's data; without the wait; with a zero-time wait; from the
    next run's slice; of every page, zero ones too;
  - PROBE: a wrong hash; the last offset off by one; the VAs of every run; no snapshot after a take-back; the first 4
    take-backs at a timeout instead of the last 4; a still-skipped run taken for a taken-back one;
  - SCRATCH_WATCH: never flags; no rate limit;
  - the copy line made a kind the quiet filter drops (`timing: t … s after that wait …`).

**The CPU test `zcb0401.cpp`.** Modes `on`, `off` and `unset`, each in a fresh directory (it writes its zero list
there). Every mode turns the zero skip on with the test's list, so off and unset show e8's skip.
- `on` sets `EXCLUDE=0x5800000,0X4200000,xyz,0x123,` (two entries, three bad ones), `COPYBACK=1`, `PROBE=on`,
  `SCRATCH_WATCH=1`. `off` sets `off`, `0`, `off`, `0`. `unset` unsets all four.
- The cases:
  - the switches and their four lines;
  - the parse of both grammars (good, bad, empty, off, the 16-entry cap);
  - the exclusion by file offset (an entry inside a run is no match; the heap's base counts);
  - the summary (count, first, last, hash against the test's own FNV);
  - the watch's rule (first line, the gap, a pending change, all zero again, the 64-line cap);
  - the copy's chunk selection on a memfd of its own (CPU data kept, non-zero pages only, a failed write counted);
  - the session: placement with the exclusion; a CPU write; a canary hit whose wait lets a job write into the slice
    (the copy carries that write; a chunk taken back before and a chunk the CPU wrote stay as they were); a timeout
    (the two take-backs, a taken-back and two still-skipped runs from a WRITE_DATA, a user-data pair and the buffer);
    a hit whose wait hits its bound; three CPU writes; the real watch thread; a later timeout (the last 4 of 6, the
    scratch BO dirty);
  - every line through the real `journal_quiet_kind`: kind 0, or -1 for the timeout lines.
- Off and unset: the same take-backs and bytes as on except the excluded run's 2 MiB; no wait, no copy (the chunks read
  zeros), no line but the four switch lines and the pure exclusion case's.
- Last line `zcb0401: <mode> N of N; end`, exit 0 only after it; a 60-s watchdog.
- **Gate row:** `zcb0401.cpp src/libs/bc5LleAgc.cpp`, run as `zcb0401 on`, `zcb0401 off` and `zcb0401 unset`, each in a
  fresh directory.
- **Edit row:** `zcb mkzcb0401.py - src/libs/bc5LleAgc.cpp:bd1811690b685369194602027b61a2d5:2fcf42d2d7528e269d821444ee4fbe9e`.
- **For `box0401.sh`'s strings check:** `BC5_DIRECT_ZERO_SKIP_EXCLUDE`, `zero skip copy-back (exp 0401 e9 zcb)`,
  `scratch watch (exp 0401 e9 zcb)`.

**Sources.**
- `hang1954-0401.md`, sections "Deep analysis 2026-11-05 (after e8)" and "Box reads after the analysis".
- Exp 0379: `experiments/0379-zero-skip/raw/zskip_block.cpp`, `backend/include/bc5/zero_skip.hpp`;
  `zsk0401-notes.md` (the skip in this unit, its TODO(verify)).
- `backend/include/bc5/direct.hpp` and `backend/src/direct.cpp` (`Device::wait_idle`, `import_memfd`, F_SEAL_SHRINK);
  `backend/src/policy.cpp` (`memory_operands`).
- The unit: exp 0024's jobs in flight and completion thread, `submit_now`, `timeout_probe` (exp 0160), the quiet
  filter (`cap0401-notes.md`).
- memfd_create(2), fcntl(2) (file seals), lseek(2) (SEEK_DATA).
- LESSONS.md R13, R21 (what a probe reading proves), R41 (the switch grammar), R44 (anchors and their effect), R49 (shared
  state between threads).

**Files** (md5 of the content with LF line ends, as git stores it).

| file | md5 |
|---|---|
| `mkzcb0401.py` | `2a2b7ea775359272785fdfc23d4d035c` |
| `zcb0401.cpp` | `1761a94f53ddc0d2c5d815da6cb636e5` |
| input `src/libs/bc5LleAgc.cpp` (e8) | `bd1811690b685369194602027b61a2d5` |
| output `src/libs/bc5LleAgc.cpp` | `2fcf42d2d7528e269d821444ee4fbe9e` |
