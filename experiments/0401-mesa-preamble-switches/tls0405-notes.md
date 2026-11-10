# Experiment 0401 series e5: the patched TLS loads keep RFLAGS and their neighbours (KYTY_BC5_TLS_FIXES)

Exp 0405, README top-32 ranks 3 and 4: `raw/r2-kyty-sharpemu.md` §4.1 and §5 items 3-4, and `raw/r2-parts/KL.md` rows
KL01 and KL02. Port group tag `tls`. Unit: `src/loader/runtimeLinker.cpp` of the e5 input tree (the base tree's: KytyPlus
`f266548` + patch 0001; e4 did not change it), md5 `e94b25b8b37d36d97a074ea02723b733`, LF line endings.

This is the riskiest group of e5. It rewrites the guest's code at load time, for every title (ours included) whose main
ELF has `mov <reg>,qword ptr fs:[0]`. With the switch off, the bytes written are exactly today's: the jit.h structs,
and today's scan, moved but unchanged.

## How the patch works today

`PatchProgram` (input 1491-1568) scans each executable segment of a non-shared program with a TLS handler for
`64 48 8B /r 25 00 00 00 00`, after up to three `0x66` bytes. It writes a 9-byte `Jit::Call9` over the load:
`E8 rel32 48 89 C0 90`, then a nop for each counted `0x66`. The call goes to `handler_vaddr` for rax, or to the
register's `Jit::TlsRegStub` at `handler_vaddr + 0x100 + reg*32`.

`SetupTlsHandler` (input 3110-3139) writes the handler:
- `Jit::SafeCall` at `handler_vaddr`. It saves the volatile registers and RFLAGS, aligns the stack, calls
  `TlsMainGetAddr` (MS ABI) and restores them.
- One `Jit::TlsRegStub` per register (rcx, rdx, rbx, rbp, rsi, rdi). Each pushes rax, calls SafeCall, moves rax into
  the register and pops rax.

`loader/jit.h` holds all three structs (input 68-161).

## Per-item verdicts

| Item | Verdict | Source | Our code (input) |
|---|---|---|---|
| KL01: the TLS-load stubs keep RFLAGS | **ported** (switch item `kl01`) | KytyPS5 `dfec14a` `src/loader/jit.h:43-117` (TlsRegStub 43-72, SafeCall 74-117), GPL-2.0 | `loader/jit.h:107-116` (TlsRegStub `sub`/`add rsp,0x80`), `127` and `157-158` (SafeCall) |
| KL02: the call goes at the `0x64` byte, as a REX.W call; no scan under 9 bytes | **ported** (switch item `kl02`) | KytyPS5 `dfec14a` `src/loader/jit.h:21-41` (Call9) and `src/loader/runtimeLinker.cpp:968-1016` (the scan; its comment at 1007-1009), GPL-2.0 | `loader/jit.h:68-87`; `loader/runtimeLinker.cpp:1519-1567` |

Provenance cross-check: KytyPlus upstream (`refs/Coder787-source_KytyPlus` at `3eee96a`) carries the same KL01 stubs and
the same REX.W `Call9` in its `src/loader/jit.h`. Its scan still writes the call at the first `0x66` (runtimeLinker.cpp
1416-1449). Nothing in either source is marked as coming from an SDK, firmware or a disassembly.

### KL01: what is wrong today

The original `mov reg,fs:[0]` leaves RFLAGS alone, but the stubs do not. TlsRegStub runs `sub rsp,0x80` before its
call and `add rsp,0x80` after it. SafeCall does the same around its `pushfq`/`popfq`, and its `sub` runs before the
`pushfq`, so even the saved copy is already wrong. The guest therefore gets the flags of the last `add`.

A compare that the compiler scheduled across the TLS load then branches on those flags. Measured by tls0405 on the
laptop: all six flags set before the call come back all clear.

**The fix:**
- `lea rsp,[rsp-0x80]` (`48 8D 64 24 80`) plus a 2-byte nop (`66 90`). These are the same 7 bytes as the `sub`.
- `lea rsp,[rsp+0x80]` (`48 8D A4 24 80 00 00 00`), 8 bytes. `ret` moves one byte later and the stub has one nop less.
- `lea` writes no flag.
- The call and data offsets do not move: TlsRegStub `code[9]`, `code[13]` and `code[15]`, SafeCall `code[0x22]`.

### KL02: what is wrong today

The scan matches raw bytes. It counts a `0x66` that ends the previous instruction (`cmp al,0x66` = `3C 66`) as a prefix
and writes its `E8` over it. That breaks the instruction before the TLS load.

With four `0x66` bytes, the scan counts three and leaves the first in front of a plain `E8`. On AMD, `66 E8` is a 16-bit
call (see "TODO(verify)" below).

A segment under 9 bytes makes `start + size - 9` point before the start. Today's loop then does not run, but the
pointer arithmetic is undefined behaviour.

**The fix:**
- The call goes at the `0x64` byte. The counted `0x66` bytes stay where they are, and there is no nop fill.
- The call is `48 E8 rel32 48 89 C0`. Its REX.W keeps any `0x66` left in front of it from making it a 16-bit call.
- `ptr += prefix_count + 9 - 1`, as KytyPS5 has it.
- The displacement is compared with `memcmp` (KytyPS5's form; today's code reads an unaligned `uint32_t`; the result is
  the same).
- Under 9 bytes, nothing is scanned.

**TODO(verify):** the AMD64 APM vol. 3 section that gives REX.W precedence over `0x66` for a near CALL. The APM is not on
disk.

Supporting evidence, a decoder model and not the vendor manual: Zydis (MIT), vendored in `refs/Inori_GPCS4` `88480de`
`3rdParty/zydis`.
- `include/Zydis/Decoder.h:70-80`: in "AMD-branch mode", `0x66` is not ignored and makes a near branch 16-bit, while
  Intel ignores it.
- `src/Decoder.c:3353-3410` (`operand_size_map`): the rows for default and default-64-bit operand size give 64 bits for
  `66` + REX.W in 64-bit mode.

The box's Zen 2 settles it by measurement. tls0405 cases 12 and 14 run `66 48 E8` and `66 66 66 66 48 E8` with kl02
on; a 16-bit call would fault and print a FAIL line. The laptop is Intel (GenuineIntel family 6 model 0x8e), so it does
not answer the AMD question.

## What changed (output `src/loader/runtimeLinker.cpp`, md5 `aba94c24ad35a1c944ad3bd5843b13ef`)

`loader/jit.h` is **not edited**: the common brief allows no header edits.
- Its only includer is `runtimeLinker.cpp`. `kernel/syscallDispatcher.h` mentions it only in a comment, and a grep of
  the input tree for `include.*jit` finds nothing else. tls0405.cpp includes it read only.
- KytyPS5's three structs go into `runtimeLinker.cpp` instead, in an anonymous namespace:
  `Bc5TlsCall9`, `Bc5TlsRegStub`, `Bc5TlsSafeCall`.
- Their bytes are checked equal to KytyPS5's jit.h by extraction (laptop script).
- `static_assert`s pin their sizes to jit.h's.
- Stub offsets come from `Jit::TlsRegStub::GetOffset` on both paths.

The edits, with output line numbers:
- **1491-1704: block inserted before `PatchProgram`.** It holds the switch (`Bc5TlsFixesParse`, `Bc5Tls0405Items`), the
  three structs, KL02's scan `Bc5TlsPatchTlsLoadsKl02` (1659-1699), and declarations of the two switch-chosen
  functions.
- **1734-1739: PatchProgram's TLS block.** Its `if` keeps its condition and now calls
  `Bc5Tls0405PatchTlsLoads(address, size, program->tls.handler_vaddr)`, then closes PatchProgram.
- **1741-1799: `Bc5Tls0405PatchTlsLoads`.**
  - With `kl02` on, it calls the KL02 scan and returns.
  - Otherwise it runs today's scan: PatchProgram's old lines, at their old place. The old `if` line is now a plain
    `{` block.
  - The only changed tokens are `program->tls.handler_vaddr` → `handler_vaddr` at 1789-1790.
- **3341-3375: `Bc5Tls0405WriteTlsHandler`, before SetupTlsHandler.**
  - With `kl01` on, it writes KytyPS5's SafeCall and TlsRegStubs at the same addresses.
  - Otherwise it writes SetupTlsHandler's old lines (3360-3374), copied by the script from the asserted original.
  - The only changes in those lines are `program->tls.handler_vaddr` → `handler_vaddr` (3×) and `TlsMainGetAddr` →
    `func` (1×).
- **3386-3388: in SetupTlsHandler.** The 14 moved lines are replaced by the call
  `Bc5Tls0405WriteTlsHandler(program->tls.handler_vaddr, TlsMainGetAddr)`. `ProtectGuestMemory` and
  `FlushInstructionCache` follow as before.

**The switch, `KYTY_BC5_TLS_FIXES`:**
- Unset, empty or `0`: off.
- Any other value: both items on, unless the value names items (comma-separated `kl01`, `kl02`); then only those. This
  is e4's `KYTY_BC5_AUDIO_FIXES` reading, so an unknown word such as `foo` turns both on.
- Read once, at the first TLS scan or handler write of the main program.
- Journal line on stderr: `[bc5] exp 0405: tls fixes on (items: kl01 kl02)` (or the items named), or
  `[bc5] exp 0405: tls fixes off`.

## The CPU test (tls0405.cpp, 19 cases)

**Build:** `build0401.py ... src/loader/runtimeLinker.cpp=<out>/src/loader/runtimeLinker.cpp --gate tls0405.cpp
<dir>/tls0405 --like src/loader/runtimeLinker.cpp`.

**Rows:** `KYTY_BC5_TLS_FIXES=1`, `=0` and unset, each in a fresh directory. The last line is `tls0405: on 19 of 19; end`
or `tls0405: off 19 of 19; end`; exit 0 only then. Partial lists (`kl01`, `kl02`) also run, and every case follows its
own item.

**How it runs:**
- It calls the unit's own `Bc5Tls0405Items`, `Bc5Tls0405WriteTlsHandler` and `Bc5Tls0405PatchTlsLoads`. These are
  declared in the test; there is no header.
- Everything happens in mmap'd pages of `0xCC`. Pages are written RW, then `mprotect`ed to R+X, then run.
- The asm runner steps over the red zone with `lea`, sets RFLAGS with `popfq`, calls the code and reads RFLAGS with
  `pushfq`.
- A fault prints a FAIL line naming the case (exit 4). A 20 s watchdog prints a FAIL line (exit 3).
- No game, GPU, window, sound device or network is needed, and no file is written.

**Cases:**
- 1: the unit reads the switch as the test does.
- 2: the test's "today" sequences equal jit.h's own `SafeCall`, `TlsRegStub` and `Call9`.
- **(a)** 3-5: SafeCall's 0x90 bytes, the six TlsRegStubs (rel32 and output register), and no other byte of the page.
  - On: KytyPS5's lea form.
  - Off: today's sub/add form.
- **(b)** 6-9: rax through SafeCall, and rbx through its TlsRegStub (rax must survive), each with CF PF AF ZF SF OF all
  set and all clear.
  - kl01 on: the six must survive and the register must hold the handler's value.
  - Off: the value is checked; the flags are measured and printed, not asserted.
- **(c)** 10-19: the scan over synthetic code. The whole two-page region is compared with the expected one, so any
  byte changed outside the instruction fails.
  - Inputs: `3C 66 |load`; three `0x66` (rbx); one `0x66`; none; four `0x66`; two loads in a row; a 9-byte segment that
    is exactly the load; 8- and 5-byte segments; five near-misses (`fs:[0x28]`, `gs:[0]`, `fs:[rsp+8]`, `eax`, `r8`).
  - The patched code then runs where its bytes can.
  - Off, cases 10 and 14 are recorded and not run: today's bytes break the code there.

## Verified on the laptop (no box access)

**Script:**
- `mktls0405.py e4tree <out>` prints `src/loader/runtimeLinker.cpp aba94c24ad35a1c944ad3bd5843b13ef`. Both inputs'
  md5s are asserted; jit.h is `8b5a53504af3ca127c1ab4fe9b55ee45`.
- Run on its own output, it stops with "has the edit already" (exit 1) and writes nothing.
- Undoing every replacement gives the input back byte for byte.
- `difflib` shows exactly 16 removed lines: the 2 SetFunc lines whose token changed, and the 14 moved SetupTlsHandler
  lines.
- Braces, parentheses and brackets balance in each edit and in the whole output.
- The inserted text is ASCII; the input's non-ASCII byte count is unchanged.

**Syntax:**
- Tool: Visual Studio's clang++ 22.1.3, `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, in the tree's Windows
  configuration.
- Setup: stand-in `cmake_config.h`; stand-ins for `execinfo.h`/`Dl_info` and `tracy/Tracy.hpp`; fmt from
  `refs/Inori_GPCS4`; magic_enum from `refs/InoriRus_Kyty`; `-Wno-deprecated-declarations
  -Wno-deprecated-literal-operator` for the STL and fmt headers.
- Results:
  - Input and output units: both clean.
  - Under `-Wshadow -Wconversion -Wcast-align`, both have the same 9 warnings. The only one in the edited region is
    today's `GetOffset(reg)` narrowing, in the moved scan line 1790.
  - tls0405.cpp: clean, with stand-ins for `sys/mman.h`, `signal.h` (`sigaction`, `sigaltstack`) and `unistd.h`.

**Stand-in run on the laptop CPU (Intel):**
- Setup: the test, plus the unit's experiment code extracted from the output (the block and the two functions, today's
  lines included), with LOGF/EXIT stubs and VirtualAlloc/VirtualProtect in place of mmap/mprotect.
- Results:
  - `=1`, `=0`, unset, `kl01`, `kl02`, `kl02,kl01`, `foo` and empty: all `19 of 19; end`, each with the right journal
    line.
  - Off, measured: six flags set → all six clear after the stub; that is the KL01 defect.
  - Case 10, off: `3c e8 fa ee ff ff 48 89 c0 90 90 c3`. Today's patch overwrites cmp's operand.
  - Case 10, on: `3c 66 48 e8 ... 48 89 c0 c3`, and it runs.
- Negative control: the same test against a stand-in whose switch never turns on (today's code) with `=1` fails 12 of
  19 (cases 3-6, 8 and 10-16). So the test can tell the two apart.

**Not checked:**
- Linux headers and the box's clang (the box builds with clang++; its warnings may differ).
- The real link.
- The run on AMD, including the REX.W question.
- The real `PatchProgram` and `SetupTlsHandler` callers.
- A title boot with the switch on.

## Risks

- Both items change the bytes of every title's patched TLS loads. A mistake shows at boot (a fault at a TLS site) or as
  a wrong branch. The switch is off by default and off is today's bytes. Boot both titles with `=1` before anything
  else.
- **KL02 on:**
  - A real `0x66` stays in front of `48 E8`. If an AMD CPU ignored REX.W there, the call would be 16-bit and the title
    would fault at its first TLS load. The box gate measures this first (cases 12 and 14).
  - Instruction length is unchanged: the patch is 9 bytes in place of 9.
- **KL01 on:** the stubs grow by one byte inside their fixed 32-byte and 0x90-byte slots. Neither reaches the next slot;
  case 5 checks the page.
- **Not addressed, found while reading:**
  - The patched site's own `call` writes its return address at `[rsp-8]`, inside the guest's red zone, before the
    stub's red-zone skip. This is the same in KytyPS5.
  - SafeCall does not save xmm0-5, which an MS-ABI callee may clobber.
  - The scan only matches REX `48`, so loads into r8-r15 (`4C`) are not patched; case 19 shows them untouched.
  - All three are pre-existing and need their own items.

## Files

| File | md5 |
|---|---|
| `mktls0405.py` (new) | `1dfb208747d3c14254c66576b0617cc7` |
| `tls0405.cpp` (new) | `3a8819507c719b95c93bb8b2d426d2a5` |
| `tls0405-notes.md` (new) | this file |
| in: `src/loader/runtimeLinker.cpp` (base tree) | `e94b25b8b37d36d97a074ea02723b733` |
| out: `src/loader/runtimeLinker.cpp` | `aba94c24ad35a1c944ad3bd5843b13ef` |
| read only: `src/loader/jit.h` (not edited) | `8b5a53504af3ca127c1ab4fe9b55ee45` |
