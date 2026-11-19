# Experiment 0434: ASTRO BOT's GPU fault on entering Bathhouse Battle

Status: cause found offline; fix ud434 written and CPU-tested; private build and the maintainer's
reproduction pending. Branch `exp/0434-astro-k1-write`.

## Question

The maintainer's ASTRO BOT (PPSA21567) crashes every time he enters the level *Bathhouse Battle*
(Serpent Starway galaxy) from his only save; the crash comes during the level's loading. It happens on
the shared lean and normal builds of patch `59f00d27` and on the pre-pack lean build (`d1388db0`),
so port pack 1 (exp 0433) is not the cause. Which job writes where, why does it fault, what does the
PS5 do, and what is the simplest correct fix at the source (no learned window, no recovery)?

## Setup

Offline, from the box's records (read-only copy under the top session's GO of 2026-11-19, nothing
committed; cited by path only):

- fault records `~/bc5-data/captures/faults/20261119-140627`, `-140758`, `-141432` (record.txt,
  layout-views.txt, journal-tail.txt of 140758);
- the normal run's capture `~/bc5-data/captures/play-20261119-1406/gc/direct.log`;
- the kernel's lines for 14:05–14:16 (`journalctl -k`);
- devcoredump `~/bc5-data/captures/devcoredump/20261119-140758-devcd4.txt` (the timed-out gfx job's
  IB, 296,984 dwords, and the CP registers).

The patch's own code read from `backend/kytyplus-patches/0001-bc5-lle-agc.patch` (patch `59f00d27`;
its `src/libs/bc5LleAgc.cpp` reconstructs to md5 `8eb42a10`).

## Result

### What faulted (all three records alike)

- [M] A submission timed out after 2 s, 65–84 s after start; the kernel's fault: address
  0x314cb6000, `GCVM_L2_PROTECTION_FAULT_STATUS` 0x006C1071 (0x007C1071 in the third run),
  `Faulty UTCL2 client ID: TCP (0x8)`, `PERMISSION_FAULTS: 0x7`, `MAPPING_ERROR: 0x0`, `RW: 0x1`
  (journal 14:06:25). So a shader's vector-memory access (TCP), a WRITE, to a page that HAS a
  mapping without write permission.
- [M] The host's record: the address is 0x92a000 into the view 0x31438c000+0x1408000 of
  `orbis_user_malloc` (direct file, LAZY by the launcher's `BC5_DIRECT_LAZY_NAMES`); its 2 MiB chunk
  was never written by the CPU and is not imported; `k1r ... a GPU WRITE (kind K1w)`. A never-written
  chunk under a lazy view carries K1r's read-only zero cover (exp 0412, F836), which matches the
  kernel's permission fault. ("GPU mapping: no" in the record is the host's view, where a K1r cover
  counts as a hole, cv412.)
- [M] The timed-out job is a dcb of 295,101 dwords (ordinary frames: 16–20 k), Bathhouse Battle's
  load. `CP_IB1_BUFSZ` 0x38a38 of `CP_IB1_CMD_BUFSZ` 0x48818: the CP had fetched about 64,984
  dwords.
- [M] The IB holds the faulting address in exactly one form: at dword 64,209 (and again at
  64,272, 296,084, 296,209, 296,261) a `SET_SH_REG` (op 0x76) writes `COMPUTE_USER_DATA_0..7`
  (register offset 0x240) with two inline buffer descriptors:
  - V# 0: base 0x5_0cf7d5c0, stride 1, 2048 records;
  - V# 1: base 0x3_14cb62dc, stride 1, 16 records — 16 bytes inside the faulted page;
  followed at 64,219 by `DISPATCH_DIRECT` 64×1×1. A small compute job that writes a 16-byte
  result into memory the title took from its CPU heap. Nothing else in the IB names
  [0x31438c000, +0x1408000) in a raw or a >>8 address form.
  (Register 0x240 = COMPUTE_USER_DATA_0 and the V# layout: AMD RDNA ISA, "Buffer Resource
  Descriptor"; TODO(verify): cite the exact table of the public RDNA1 ISA document.)

### Why the host did not map it writable

The host imports, before a submit, the memory a packet names itself (k1f412: its operands, on by
default) and the render/depth targets (the CB/DB hints). A buffer that a shader reaches through a
descriptor in its user data is named by no packet operand, so under a lazy view its never-written
chunk keeps the read-only zero cover and the shader's store faults. Exp 0412's dt412 decoded such
descriptors, but as a log-only catcher that also read tables, it cost 5 flips/s and was parked
(exp 0412 README, run n12D1).

### What the PS5 does

Every page the title maps for the GPU is the GPU's to read and write as mapped; the CPU heap is plain
memory there. The fault is ours: the lazy rule plus K1r's read-only cover.

### The fix: ud434 (`BC5_DIRECT_UD_TARGETS`, on by default in the test build, `=0` off)

Inside the k1f412 pass that already walks every packet before every submit: for each `SET_SH_REG` /
`SET_SH_REG_INDEX` into a stage's user-data registers (PS, VS, GS, ES, HS, LS at SH offsets 0x0c,
0x4c, 0x8c, 0xcc, 0x10c, 0x14c, 32 each; compute 0x240, 16), every quad 4-aligned to the stage's
first register whose dword 3 has TYPE 0 is read as a V# (base dword 0 + dword 1 bits 15:0, below
2^40; bytes = stride × records, or records with stride 0; cut at 256 MiB). When the range is not
mapped and lies under a view of direct memory, its chunks are imported (`direct_force`, as k1f412
does) before the submit. No tables are read, nothing is learned, nothing recovers after a fault.
A false positive costs one 2 MiB pin, never a fault. The switch reads `std::getenv`, so it can be
turned off in the lean test build too. The change: `ud434-bc5LleAgc.diff` (one unit,
`src/libs/bc5LleAgc.cpp`, md5 `8eb42a10` → `e8ea29c1`), its decoder `ud434.inc`.

CPU test (laptop, VS clang++ 20, `-std=c++20 -Wall -Wextra -Werror`): `ud434_test.cpp`, **17 of 17**,
among them the faulting packet and the one after it verbatim from the devcoredump. Mutation check:
dropping the alignment test fails 2 cases, dropping the TYPE test fails 1; a third check (a quad
crossing a stage's end) was removed as dead code, since every stage size is a multiple of 4.

### Not covered by ud434 (stated, not tested)

A V# that reaches the shader through a table in memory (loaded by `LOAD_SH_REG_INDEX` or read by the
shader through a pointer), and image descriptors (T#) for storage images. The faulting job used the
inline form; if the reproduction faults again, the record will name the next form.

### The second title

The same class can hit it: any non-eager heap (by data or lazy) has K1r covers on its never-written
chunks, and exp 0412's arm b1 (F841) ended in a GPU WRITE under the read-only cover (0x121a807000,
TCP) in CommitIABufferAllocator. ud434 covers its inline-V# case. What it adds to the second title's
pins (memory wall, F841) is to be counted in the test from ud434's journal line.

### The combined private test build (2026-11-19 14:34, the top session's GO)

One binary pair with ud434 and exp 0435's per-title settings (`KYTY_BC5_TITLE_SETTINGS`, its kit
`apply0435.py` / `title_settings.hpp` / `units.sha256` from branch `exp/0435-per-game-settings` at
`33a97b61`), built by `box0434.sh build e8ea29c1…` (log: `raw/build-combined-20261119.txt`):

- [M] copies of the shared tree's files (patch `59f00d27`, checked against 0435's `units.sha256` and
  `bc5LleAgc.cpp` `8eb42a10`) in `~/bc5-work/exp0434/src`, `apply0435.py` on them (5 files edited,
  `title_settings.hpp` written), the patched `bc5LleAgc.cpp` (`e8ea29c1`) put in. The two changes
  share no file; 0435's header edits only add function declarations, so the 4 changed units
  (`bc5LleAgc.cpp`, `hostInput.cpp`, `window.cpp`, `main.cpp`) are compiled with each shared build's
  own command and relinked with its objects otherwise.
- [M] normal `~/bc5-work/exp0434/normal/kyty_emulator` **`94eac89c`**, lean
  `~/bc5-work/exp0434/lean/kyty_emulator` **`babd46fd`**; 0 errors; 10 and 11 warnings, all in the
  shared files at lines before ud434's insertion (6895) or in `stringUtils.h`, so none is ud434's.
  Both binaries hold `BC5_DIRECT_UD_TARGETS` and `KYTY_BC5_TITLE_SETTINGS`; the normal one holds
  ud434's journal line (the lean one compiles the journal out).
- [M] shared tree files, normal `efc28a30`, lean `d8b75137`, archive `51db2c91`, `play-any.sh`
  `fc7a1395`, `play-astro.sh` `e943bd8f`, `play-pkg.sh` `47426d8e`, `lean-session.sh` `1f1be812`,
  `input.cfg` `8115a7ff`: the same before and after.
- Test launcher `~/bc5-work/exp0434/play-test.sh` (`5a7a3c2f`): the shared `play-any.sh`, unchanged,
  with `BC5_EMU` / `BC5_EMU_LEAN` set to the private binaries (`BC5_LEAN=1` picks the lean one, as in
  the shared shortcut). `BC5_DIRECT_UD_TARGETS=0` or `KYTY_BC5_TITLE_SETTINGS=0` turns either change
  off with no build.
- **Correction (the top session, before the play):** `play-test.sh` would NOT have tested ASTRO BOT.
  `play-astro.sh` hard-codes its emulator path and ignores `BC5_EMU`, so the title would have run the
  shared binary. `play-pkg.sh` (line 25) lets `BC5_EMU` (normal) override lean. The test runs from the
  top's `~/bc5-work/exp0434/top/play-test-0434.sh` instead: private copies of `play-astro.sh` and
  `play-pkg.sh` with the emulator path replaced, passed in through `BC5_IMAGE_SCRIPT` /
  `BC5_PKG_SCRIPT`, and `BC5_EMU` set only when not lean; a dry run picks the copy. His shortcut
  "BC5 test 0434+0435 (lean, host)" points at it. LESSONS R66.

## Verdict

Pending: the maintainer's reproduction on Bathhouse Battle on the combined build (ud434 on; the
fault, if any, writes a new record), and the second title's import count from ud434's journal line.
