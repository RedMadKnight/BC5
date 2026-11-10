# Experiment 0401 series e5, tag `gpu`: experiment 0405 R3's GPU items in the soft CP and the gc ioctls

`mkgpu0405.py` edits `src/libs/bc5LleAgc.cpp` of the e5 input tree (KytyPlus f266548 + patch 0001 + e4's units). It
touches two regions only: the soft CP (`namespace SoftCp`, the CPU executor of packets) and the gc ioctl handler
(`gc_ioctl`, plus one seam right after it). The specs are exp 0405 `raw/r3-gpu-memory.md`, "e4-now port specs".

**Hard limit kept: nothing changes what is submitted to amdgpu.** The policy (`backend/policy/pm4-policy.tsv`,
`default-op drop`) still NOPs MEM_SEMAPHORE (0x39), COND_WRITE (0x45) and REWIND (0x59) on the GPU path. The changes
are of three kinds:

- the soft CP's own execution;
- host events after a fence;
- catchers (a count, plus one journal line per kind).

The backend archive and every header are untouched.

Line numbers `out:N` refer to the output unit (md5 `8d71e9f6a5259dc45f3be5baf6bc8bfa`). The output is the input plus
inserted lines only: `diff` shows no removed line. The script also reverts its edit in memory and asserts that the input
comes back byte for byte.

## Switches and journal

Each switch is off by default and read once, at the first use (`r3gpu()`, out:508). The reading is
`bc5::env_on(std::getenv(...))`, from `backend/include/bc5/env_flag.hpp`. A build without `KYTY_BC5_DIRECT` uses the
same reading, inlined.

At the first use, one line goes to stderr: `[bc5] exp 0405: gpu on (items: BC5_R3_..., ...)` or `[bc5] exp 0405: gpu off`.

Journal lines go through `Direct::journal`, to `BC5_GC_DUMP_DIR/direct.log`:

- each kind is journaled once, at its first occurrence, with where it was (the packet address, its offset in the walked
  buffer, and the buffer `submit()` was handed);
- after that it is only counted;
- a summary `exp 0405 gpu: t … s: MEM_SEMAPHORE set/add/wait/other …; REWIND …; dropped by the policy … (by opcode: 39:n …);
  custom NOPs … (by sub-code: 17:n …); submit-EOP events …; COND_WRITE …; wait idle …; 100-MHz timestamps …` is written
  at most every 10 s, and only when a count has moved. It comes from `SoftCp::submit` (out:1272) and only when any
  switch is on.

The first-of-kind lines:

| Item | Line |
|---|---|
| G2 | `MEM_SEMAPHORE not executed`, `MEM_SEMAPHORE wait … not held`, `MEM_SEMAPHORE signal (set 1/add 1) … executed by the soft CP` |
| G4 | `REWIND with VALID clear (dword 1 …), …; n of the m dwords after it in that buffer are not 0` |
| G8 | `opcode 0xNN (header …) is NOP-ed by the policy on the GPU path`, once per opcode; `custom NOP sub-code 0xNN`, once per sub-code |
| G11 | `COND_WRITE not executed (…)`, `COND_WRITE executed by the soft CP (…)` |
| G6 | `submit-and-write-EOP ioctl: the graphics EOP event (0x40) with … raised after the call's buffers[ (behind the held chain)]` |
| G12 | `wait-idle ioctl waited … ms`; `wait-idle ioctl gave up after …` |

## Items

### G2 `BC5_R3_MEMSEM_SIGNAL`: MEM_SEMAPHORE signal in the soft CP. **Ported.**

**Source.** All GPL; behaviour only.

- The packet form agrees across three projects:
  - KytyPS5 dfec14a `src/graphics/guest_gpu/command_processor/pm4Handlers.cpp:2077-2088` (header `0xc0023900`, 4 dwords)
    and `graphicsRun.cpp:277-285` (GPL-2.0);
  - AnyPS5 4f41f4c37 `core/libs/prx/libSceAgcDriver/Execution/src/Pm4.cpp:507-512` (size 4) and `:1130-1147` (signal,
    wait), plus `docs/dev/debt/libSceAgcDriver.md:62` (GPL-2.0-only);
  - sharpemu 514d766 `src/SharpEmu.Libs/Agc/AgcExports.MemSemaphore.cs:47-58`, the builder
    `op<<29 | type<<20 | mailbox<<16` (GPL-2.0-or-later).
- shadPS4 60c42b9 `src/video_core/amdgpu/pm4_cmds.h` `PM4CmdMemSemaphore` gives the field names (the PS4's 3-dword form)
  and `liverpool.cpp:799-809` (GPL-2.0-or-later).
- Mesa ab2374a `src/amd/common/sid.h:88` (MIT, the opcode only).

**What changed.**

- `r3gpu_mem_semaphore` (out:574-620) and `case IT_MEM_SEMAPHORE` in `execute()` (out:1233-1239).
- The 4-dword form only: the address is `p[1] & ~7` with the high bits from `p[2]`.
- A signal (SEM_SEL 6) with bit 20 set does `__atomic_store_n(1)`; with bit 20 clear it does `__atomic_fetch_add(1)`.
- A wait (SEM_SEL 7) is counted and journaled only. G3 is later.
- These are counted as "other" and not executed: another length, address 0, or another SEM_SEL.
- It runs only when the GPU did not run the packet (`!done`); the GPU always NOPs it.
- **The hardware path still NOPs the packet through the backend policy** (`tsv:11`). Only the soft CP's pass signals.
- Off, the case does exactly what `default:` does today (`g_skipped[op]++`).

**Tests** (case "G2 MEM_SEMAPHORE signal", 11 checks):

- set → 1, add → 2, add → 3;
- a wait leaves the word and the buffer goes on (a WRITE_DATA after it lands);
- the 3-dword form, address 0 and SEM_SEL 5 are not executed;
- address bits 2:0 are ignored;
- the four counters;
- off: the word stays 5 throughout and every counter stays 0.

**Risks.**

- The signal happens when the soft CP walks the buffer. For posted replays (submit lists, ring slices, chains: the
  launchers' `BC5_DIRECT_CHAIN=2`) that is after the fence. For IB-packet submissions without a chain it is at
  submission. That is today's soft-CP timing for those buffers, the same as their EOP events.
- An unmapped semaphore address faults the host, like every other soft-CP write.
- The 64-bit width is inferred (AnyPS5 debt L62), not measured.

### G4 `BC5_R3_REWIND_CATCH`: REWIND with VALID clear. **Ported as a catcher on the unit side** (R3 placed it in `BE/src/policy.cpp`; the backend is not ours).

**Source.**

- AnyPS5 `Execution/include/Pm4.hpp:162-163` (RewindValid bit 31, RewindOffloadEnable bit 24) and `Pm4.cpp:497-500`.
- shadPS4 `pm4_cmds.h` `PM4CmdRewind`, and `liverpool.cpp:815-824` (waits for VALID).
- KytyPS5 `pm4Handlers.cpp:1324-1333` (header `0xc0005900`).
- Mesa `sid.h:206` ("GFX8+ [any ring]").

**What changed.** `r3gpu_rewind` (out:622-642) and `case IT_REWIND` (out:1247-1250). Nothing is executed:

- every REWIND the soft CP walks is counted;
- those with bit 31 clear are counted separately;
- the first of these is journaled, with the count of non-zero dwords after it in that buffer;
- the case still does `g_skipped[op]++`, on and off.

**Tests** (case "G4 REWIND catcher", 3 checks):

- VALID clear, VALID set, and OFFLOAD_ENABLE alone go in;
- the WRITE_DATA after an invalid REWIND still lands;
- the counts are 3 and 2 when on, 0 and 0 when off.

**Risks.** The soft CP reads guest memory when it runs (after the fence when posted), so the CPU may have set the bit
by then. The count is a lower bound. Only buffers the soft CP walks are seen (all of them by default; `BC5_GC_MODE=kyty`
skips the soft CP).

### G8 `BC5_R3_DROP_CATCH`: what the policy drops, and custom NOPs. **Ported on the unit side** (R3 placed it in `FilterStats`, which is backend).

**Source.**

- The NOP sub-codes come from two projects that agree:
  - KytyPS5 `src/graphics/guest_gpu/pm4.h:74-84` and `command_processor/pm4Dispatch.cpp:223-229`;
  - AnyPS5 `Execution/src/Pm4.cpp:223-240` (`header & 0xfc`, `(header >> 2) & 0x3f`).
- The table comes from our own `bc5::policy::Policy::builtin().op()`, a read-only query of the table the filter uses.

**What changed.** `r3gpu_drop_note` (out:644-676) is called before the soft CP's opcode switch (out:1208). It counts:

- per opcode, every type-3 packet whose policy verdict is Drop;
- per sub-code, every NOP whose bits 7:2 are not 0.

The first of each opcode and of each sub-code is journaled. Nothing is executed.

**Tests** (case "G8 drop catcher", 11 checks):

- One buffer goes in: MEM_SEMAPHORE, COND_WRITE, REWIND, WRITE_CONST_RAM 0x81, custom NOP `0xc004105c` (sub 0x17),
  a plain NOP, the filler `0xffff1000` and a WRITE_DATA.
- On: each of 0x39/0x45/0x59/0x81 is +1, and 0x37 and 0x10 are +0. Sub-code 0x17 is +1 and sub-code 0 is +0. The totals
  are 4 and 1.
- The WRITE_DATA still lands.
- Off: everything is 0.

**Risks.**

- The query cannot tell `default-op drop` from the two listed drops, 0x4a and 0x8e; both count.
- Not seen: the filter's drops in code (unmapped operands and the like), what a COND_EXEC skipped in the soft CP, and
  IBs nested deeper than 4.
- Cost when on: one table lookup per packet.
- Without `KYTY_BC5_DIRECT` only the sub-codes are counted. The test then expects 0 opcodes and says so.

### G6 `BC5_R3_SUBMIT_EOP_EVENT`: submit-and-write-EOP raises the graphics EOP. **Ported** (host event, after the fence).

**Source.** RPCSX e8ae148 (GPL-2.0):

- `rpcsx/iodev/gc.cpp:250-277`;
- `rpcsx/gpu/DeviceCtl.cpp:60-80`: `submitWriteEop`, an EVENT_WRITE_EOP with address 0, INT_SEL 2, DATA_SEL 2 and
  `eopValue`;
- `rpcsx/gpu/Pipe.cpp:20-30`: `kGcEventGfxEop = 0x40`.

**What changed.**

- `r3gpu_submit_eop` (out:711-744), called after today's submit-page store (out:9435-9437).
- It runs `fire_eop(eop_value)` on the graphics side: 0x40, plus ident 0 quietly, as for any graphics EOP of this soft
  CP. It goes through `Direct::post`:
  - asynchronous submission: after the call's jobs' fence, on `bc5-cq0`;
  - no direct path, or jobs waited at submission: at once.
- **Beyond R3's spec:** with the game thread's chain held across ioctls (`BC5_DIRECT_CHAIN=2`, the launchers' setting), a
  plain post would fire before the held chain is even submitted. Instead, RPCSX's 6-dword EVENT_WRITE_EOP (address 0, so
  nothing is written) is handed to the chain as a soft-CP replay (`Direct::chain_soft_push`), posted behind the chain's
  fence. The replay reads it later, so it lives in a 4096-slot ring.
- Off: today's (the value is stored only).

**Tests** (case "G6 …", 14 checks on, 10 off). The test registers a KytyPlus equeue with EVFILT_GRAPHICS idents 0x40
and 0, using the trigger and reset functions of `sync.cpp`'s AddEqEvent. Then:

- an ioctl with one IB (a WRITE_DATA label) and `eop_value` 0x0123456789abcdef: the label is written (on and off); on,
  both events arrive with that data, through the completion queue; off, none arrives in 300 ms;
- an empty command list with 0x42: the same;
- the counters are checked;
- `chained` is 0.

**Risks.**

- **Untested on the laptop and in the gate:** the chain path needs a device (`chain_on()` needs `g_stage == All`). It
  needs a box check with `BC5_DIRECT_CHAIN=2`.
- An EOP replay delayed past 4096 later calls would read a newer value.
- A title that also ends its buffers in a RELEASE_MEM with INT_SEL gets an extra wake-up. Waiters re-check their
  labels.
- RPCSX also waits for idle at the end of this ioctl (`gc.cpp:271`). That is not ported.

### G11 `BC5_R3_COND_WRITE`: COND_WRITE in the soft CP. **Ported.**

**Source.**

- AnyPS5 `Execution/src/Pm4.cpp:513-520` (validation: WRITE_SPACE bits 9:8 == 1, function ≤ 6) and `:736-739`
  (layout), `:1198-1206` (execute), `:589-600` (compare).
- RPCSX `rpcsx/gpu/Pipe.cpp:1266-1300` (the same layout) and `:66-88` (compare masks both sides).
- Mesa `sid.h:128`.

**What changed.**

- `r3gpu_cond_write` (out:678-709) and `case IT_COND_WRITE` (out:1240-1246).
- The packet is 9 dwords, with memory poll and memory destination. When `compare(fn, *poll, mask, ref)` is true (this
  soft CP's compare, masking both sides like RPCSX), the dword is written.
- These are counted and not executed: a register poll, a register or scratch destination, function 7, a wrong length,
  and address 0. **This deviates from R3's spec:** `compare()` answers true for 7; AnyPS5 refuses 7 and RPCSX's compare
  is false.
- Off: today's default.

**Tests** (case "G11 COND_WRITE", 18 checks):

- each function 0-6, true and false, against a poll word 0x105 with mask 0xff, plus a reference with bits outside the
  mask (RPCSX semantics: true);
- the four not-executed forms;
- the counters;
- off: no write at all.

**Risks.**

- TODO(verify): AnyPS5 masks only the value, so a reference with bits outside the mask differs.
- The same timing note as G2: it runs at the soft CP's pass.

### G12 `BC5_R3_WAIT_IDLE`: wait idle blocks. **Ported, with a narrower wait than R3's spec.**

**Source.** RPCSX `rpcsx/iodev/gc.cpp:287-293` (`waitForIdle` in 0xc0048117).

**Finding:** RPCSX's 0xc0048116 (`gc.cpp:279-285`) has its wait commented out but **no `break`**, so it falls through
into 0xc0048117's `waitForIdle`. R3 said that RPCSX does not wait there. TODO(verify) whether that is intended. Here
0xc0048116 stays as it is.

**What changed** (out:9452-9477):

- For 0xc0048117 only, after today's `chain_observe()`, with asynchronous submission the ioctl polls every 50 µs until
  `Direct::g_cq_items == 0`, bounded at 2 s.
- `g_cq_items == 0` means every queued job has passed its fence and every posted replay has run. It is the wait
  `Direct::drain()` does at the flip.
- R3 asked for `Direct::drain()` and `wait_jobs()`. They are not called: their `chain_flush` calls could close another
  thread's held chain early, which changes how the work is grouped into submissions. `g_dev->wait_idle` also needs the
  device lock.
- The bookkeeping is in `r3gpu_wait_idle_note` (out:746-752).
- Without asynchronous submission there is nothing to wait for.
- Off: today's (at once).

**Tests** (case "G12 wait idle", 8 checks in the asynchronous run). A completion-queue item that sleeps 300 ms is
queued (seam `bc5_exp0405_gpu_post`), then:

- 0xc0048117: on, the item has run when the ioctl returns; off, it has not;
- 0xc0048116: it has not, on or off;
- the counters (on 1, off 0; gave up 0).

**Risks.**

- Frame-time cost when on.
- `g_cq_items` counts the ring thread's queue (`cq1`) too, so the wait includes compute work, as the flip's drain does.
  A replay polling a label can hold it until the 2-s bound. That is journaled once and counted.

### G14 `BC5_R3_TS_100MHZ`: soft-CP timestamps at 100 MHz. **Ported.**

**Source.**

- AnyPS5 `docs/dev/debt/libSceAgcDriver.md:287`: measured on a PS5, firmware 13.40. RELEASE_MEM DATA_SEL 3 and
  COPY_DATA SRC_SEL 9 are one counter, at 98.0 and 99.8 MHz.
- AnyPS5 `Execution/src/Pm4.cpp:1178-1180` writes steady-clock ns / 10.
- Mesa `sid.h:168` (`EOP_DATA_SEL_TIMESTAMP` 3) and `:107` (`COPY_DATA_TIMESTAMP` 9).

**What changed.** `r3gpu_clock` (out:754-763) returns `now_ns() / 10`. It is used in:

- `write_timestamp_or_data` case 3 (out:817-821; RELEASE_MEM and EVENT_WRITE_EOP);
- `copy_data` case 9 (out:924-930).

DATA_SEL 4 and SRC_SEL 0xa keep ns. Off: `[[fallthrough]]` into today's ns line.

**Tests** (case "G14 timestamps", 6 checks): RELEASE_MEM DATA_SEL 3, EVENT_WRITE_EOP DATA_SEL 3 and COPY_DATA SRC_SEL 9
fall within [t0/10, t1/10] when on and within [t0, t1] when off. DATA_SEL 4 and SRC_SEL 0xa are ns either way. The count
is 3 or 0.

**Risks.** The epoch is the host's steady clock, not the GPU counter that the direct path's GPU-written timestamps
carry. TODO(verify) the box's `gpu_counter_freq` before mixing the two. A title that mixes a GPU-written stamp with a
soft-CP stamp gets a wrong delta either way.

### Held

- **G7 SET_PREDICATION:** it changes submission (brief and common rule 5).
- **Every row R3 marks "later":** G3, G5, G9, G10, G13, G15-G24.
- Not ported tonight: RPCSX's wait for idle inside 0xc020810c.

## The CPU test `gpu0405.cpp`

It calls the real unit through extern "C" seams. They are always compiled in and never called by the emulator:

- out:1289-1325: `bc5_exp0405_gpu_switches`, `_soft_submit` (→ `SoftCp::submit`), `_count`, `_drop_op`, `_nop_sub`,
  `_has_policy`, `_register_eq`, `_post`, `_async`;
- out:9596: `_gc_ioctl` (→ `gc_ioctl`).

The setup:

- It never calls `Direct::init_once`, so no device is opened and nothing is submitted.
- It initialises core, threads, config (silent) and log, as amm0401 does, minus memory. Guest memory is the test's own
  statics.
- It runs itself once more with `BC5_DIRECT_JOURNAL=min`, the unit's asynchronous completion queue, read at load. It
  also sets `GPU0405_REEXEC=1`, and `BC5_DIRECT_MEM_LINE=0` so that exp 0401's memory-line thread does not start. This
  way G6's event comes from `bc5-cq0` and G12 has a queue. If `execv` fails it runs synchronously and says so.

Output:

- 8 cases, one line each: switches, G2, G4, G8, G6, G11, G12, G14;
- **72 checks with all on, 68 with all off** (asynchronous run);
- then `gpu0405: on|off N of N; end` (or `mixed <items>`). Exit 0 only after `; end`. A 60-s watchdog prints a FAIL
  line on a hang.

Run: `BC5_R3_MEMSEM_SIGNAL=1 BC5_R3_REWIND_CATCH=1 BC5_R3_DROP_CATCH=1 BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_COND_WRITE=1
BC5_R3_WAIT_IDLE=1 BC5_R3_TS_100MHZ=1 gpu0405 on`; each `=0` → `gpu0405 off`; unset → `gpu0405 off`. Build:
`build0401.py … --gate gpu0405.cpp <out> --like src/libs/bc5LleAgc.cpp`.

## Laptop verification (no box)

- The script applies to the e5 input tree and prints `src/libs/bc5LleAgc.cpp 8d71e9f6a5259dc45f3be5baf6bc8bfa`.
- It refuses its own output (with and without `--chain`). It refuses a different md5 without `--chain`.
- With `--chain`, on a stand-in of an eq-region edit (lines added in `Kevent` and `Mmap`), it gives today's output plus
  the stand-in lines.
- Every anchor asserts exactly once and lies inside the two regions. The script asserts this.
- `diff` input→output shows insertions only. The braces balance (1909 → 1974 on both sides). The parentheses add 359
  of each kind.
- Syntax, with clang 22.1.3 from VS 18 (x86_64-pc-windows-msvc), `-fsyntax-only -ferror-limit=0 -std=c++20 -Wall
  -Wextra -Werror`, in the tree's Windows configuration: a stand-in `cmake_config.h` and fmt from `refs/Inori_GPCS4`, as
  mem0405 and svc0405 did. The unit needs a few POSIX stand-ins: `pthread.h` with `pthread_self` and
  `pthread_setname_np`; and, for the direct path, `sys/mman.h` and `unistd.h` declarations.
  - **The whole unit, without `KYTY_BC5_DIRECT`.** Input and output give the same 7 errors, and no warnings. The
    errors are MSVC's `<codecvt>` deprecation in `common/stringUtils.h`, and today's Linux-only `::mmap` at line 103.
  - **The whole unit, with `-DKYTY_BC5_DIRECT` and `backend/include`.** This configuration compiles the policy query
    and the G12 wait. Input and output give the same 30 error messages (compared without line numbers). All are in
    today's Linux-only code: `mincore`, `pread`, `memfd`/`F_ADD_SEALS`, `pthread_getname_np`, `R_OK`, MSVC's POSIX-name
    deprecations, and two `-Wmissing-field-initializers`. None lies in the inserted line ranges listed above.
  - **The extracted `SoftCp` namespace plus the two edited cases, with stubs.** This adds `-Wimplicit-fallthrough`,
    with and without `KYTY_BC5_DIRECT`: nothing in the new lines.
  - **`gpu0405.cpp`.** Checked against the tree's real headers with `-Werror`: clean with
    `-Wno-deprecated-declarations`, which is only for MSVC's POSIX-name deprecation of `execv`, plus a stand-in
    `unistd.h` declaring `setenv`.
- **Not checked:** GCC 13+, the box's real compile command, the link, and running the test. The chain path of G6 needs a
  device.

## Files

| File | md5 |
|---|---|
| `mkgpu0405.py` | `ba2459219e55cd0bedeee17ee2a9da87` |
| `gpu0405.cpp` | `9cdcfafb785c199e6e2112589545bb69` |
| input `src/libs/bc5LleAgc.cpp` | `df12bb2de3e90b8c82a234eedf0babb5` |
| output `src/libs/bc5LleAgc.cpp` | `8d71e9f6a5259dc45f3be5baf6bc8bfa` |
