# Exp 0401 series e6, tag jit: JIT shared memory (exp 0405 R3 M31) and one firmware-run libkernel row (notes, 2026-11-04)

Written for the e6 build. The inputs are e5's units from the e6 input tree (`scratchpad/e6/e5tree`):
`src/kernel/memory.cpp` (`95d9ca88…`, e5's mem output) and `src/libs/libKernel.cpp` (`b3532873…`). No header is edited;
`memoryAddressSpace.inc` (shared, read only) is not touched. Both units are LF and stay LF.

## Switches and the journal lines

- **`KYTY_BC5_JIT_SHM`** (one item, M31). Read once, at registration (`Libs::InitAll`). The first use prints one stderr
  line: `[bc5] exp 0405: jit shm on (items: create,alias,map,close)` or `[bc5] exp 0405: jit shm off`.
- **`KYTY_BC5_FW_KERNEL`** (group, item list; one item today: `notify`). Read once, at registration; one stderr line:
  `[bc5] exp 0405: fw kernel on (items: notify)` or `[bc5] exp 0405: fw kernel off`.
- A switch is on when set, non-empty and not `"0"`. `KYTY_BC5_FW_KERNEL` may name items in a comma list; any other
  value turns all of them on (e5's rule).
- **Off is today's path.** Every changed registration is an `if (switch) { new } else { today's line }`; nothing in
  memory.cpp is reachable with `KYTY_BC5_JIT_SHM` off (only the three registrations reach it). Off adds one getenv and
  the journal line per switch.

## M31 `KYTY_BC5_JIT_SHM`: the JIT shared-memory calls. Ported, from behaviour only (decision 3)

**Provenance.** Behaviour only, as the maintainer asked ("=> A, ale w taki sposób aby nie można było powiązać naszego kodu
z IDA"). Source: AnyPS5 `4f41f4c375f5abb487dbd184fbc150f31994d762` (GPL-2.0-only):
`core/libs/prx/libkernel/DirectMemory/Jit.cpp:197-237` (the three calls), `docs/dev/debt/libkernel.md:175` (what they
do, unmeasured on a console), `core/libs/prx/libkernel/File/src/Open.cpp:312-320` (close forgets a JIT descriptor),
`core/libs/tests/GuestJitSharedMemory.cpp` (the error cases, as a list of behaviours). No code was copied. Our own
names (`Bc5JitAreaCreate/Alias/Map`, `Bc5JitHandleClose`, `Bc5JitArea`, `Bc5JitHandle`, `label`, `bytes`, `ceiling`,
`handle_out`, `prot`, `where`), our own structure (a handle table of shared areas; the guest's runtime ranges for the
views) and comments. No IDA or Orbital type name and no structure layout: the calls take only scalars and pointers to a
scalar. The only things kept are the ones the behaviour forces: the argument order of each call, and the semantics of the
handle and of the address in/out. The NIDs are hashes of the public names (exp 0327's calculator, below), not taken
from any database. Orbital and IDA are not cited anywhere in the code.

**What each call does** (behaviour seen in AnyPS5's GPL code; protections are CPU read 1, write 2, execute 4; when two
protections are compared, write and execute count as read too):
- create (label, bytes, ceiling, handle out): makes a shared memory area of `bytes` whose views may never get more than
  `ceiling`, and writes a handle. The label is ignored. EINVAL when there is no handle out, `bytes` is 0 or not a
  multiple of 16 KiB, or `ceiling` has other bits. When the host runs out: EMFILE, ENFILE or ENOMEM.
- alias (handle, ceiling, handle out): one more handle on the same area, with a ceiling no wider than the handle's.
  EINVAL (no handle out, other bits), then EBADF (not an area's handle), then EACCES (a wider ceiling).
- map (handle, prot, address in/out): maps the whole area with `prot` and writes the address back. The address passed in
  is a hint only, as mmap without MAP_FIXED. EINVAL (no address, other bits), then EBADF, then EACCES (prot above the
  handle's ceiling).
- close of a handle forgets it; the views stay mapped until munmap, and writes through one view show through all others.

**Changes** (line numbers in the outputs):
- `memory.cpp` 4245-4467 (one inserted block, before e5's M1 comment; nothing else changed):
  - `Bc5JitGrants`/`Bc5JitFits` (4276-4282): the protection rule.
  - `Bc5JitArea` (4285): the host memory of an area. On Linux it is a memfd (`syscall(SYS_memfd_create)` with
    `MFD_CLOEXEC`, `ftruncate`), closed with the area's last handle.
  - `Bc5JitHandle` and a `std::map` handle table under its own mutex. Handles are our own numbers, from 0x40000 up and
    never reused. That keeps them clear of the file system's descriptors (3 up, `fileSystem.cpp:41`), the sockets
    (128-1023) and the epoll ids (1024 up, `network.cpp:1069-1075`).
  - `Bc5JitAreaCreate` (4381), `Bc5JitAreaAlias` (4400), `Bc5JitAreaMap` (4415), `Bc5JitHandleClose` (4452).
- **The host double mapping.** A view is made the way this file makes every runtime area:
  - `AllocateGuestRuntimeMemory(hint, bytes, prot, "bc5-jit", Runtime, false)` reserves the range table entry and the
    guest address range. If the hint has no room, it is called again with 0 (anywhere).
  - `Bc5JitShowArea` then replaces that range's host pages with `mmap(MAP_SHARED | MAP_FIXED)` of the area's memfd.
  - So VirtualQuery, QueryMemoryProtection, mprotect and munmap treat a view like any other committed range. munmap puts
    the placeholder back over it (`ReleaseCommitted`, `RestorePlaceholder`).
  - **The new host facility** is the memfd per area plus that one `mmap`. memory.cpp had no shareable object other than
    its two fixed stores (direct memory, private memory), and neither can be mapped twice outside its own offset rules.
    This is the smallest version.
  - Host protection: read-write, plus execute when prot has it, as this file maps every committed range. The range table
    keeps the guest's prot.
  - The areas count against no budget (AnyPS5 says the same).
  - Not Linux: create answers ENOMEM. KytyPlus on Windows is not a BC5 target.
- `libKernel.cpp`, block 1924-2036 (inside `namespace LibKernel`, at its end):
  - local declarations of the four memory.cpp functions (no header change);
  - `Bc5JitShmOn` (1946);
  - two close wrappers: `Bc5JitSceClose` (1957; a JIT handle gives OK, anything else goes to
    `FileSystem::KernelClose`) and `Bc5JitPosixClose` (1965; a JIT handle gives 0, anything else goes to
    `LibKernel::close`).
- `libKernel.cpp` registrations, each as if/else with today's line kept in the else:
  - close in the Posix library, 2764-2768;
  - `sceKernelClose`, 3710-3714;
  - close in libkernel, 3960-3964;
  - `_close`, 4051-4055;
  - the three JIT NIDs, 3773-3777, after `InitLibKernel_1_Mem`'s last line.
- **NIDs** (exp 0327's calculator: SHA-1 of the name and the salt, as `nid0401.py` has it; self-checked first on three
  known pairs; `mkjit0405.py` asserts each one):
  - `avvJ3J0H0EY` sceKernelJitCreateSharedMemory;
  - `MR221Mwo0Pc` sceKernelJitCreateAliasOfSharedMemory;
  - `YKT49TOLQWs` sceKernelJitMapSharedMemory.

  AnyPS5 registers by symbol name (its nid patcher hashes the names), so the names are its registration. shadPS4
  `60c42b9` `src/core/aerolib/aerolib.inl` lists the same three. The close NIDs `UK2Tl2DWUns`, `bY-PO6JhzhQ` and
  `NNtFaKJbPt0` (sceKernelClose, close, _close) were checked too.

**Tests (jit0405.cpp; Linux only).** Through the real `Libs::InitAll` and `Loader::SymbolDatabase`, called as a title's
import resolves them:
- case 1, registration: on, by NID and by the libkernel import key, to `Bc5JitArea*` (address and name); off, not found.
- case 2, the four close entry points: on, the wrappers; off, today's functions (address of `FileSystem::KernelClose`).
  In both modes `sceKernelClose(1)` gives EPERM and `close(1)` gives 0.
- cases 3-7, on only:
  - create, with 5 EINVAL cases;
  - alias, with 3 EACCES, 2 EINVAL and 3 EBADF cases;
  - three views (RW, RX through an RX alias, R through a read alias). Each is 16 KiB aligned, in the guest range,
    `memfd:bc5-jit` in `/proc/self/maps`, and QueryMemoryProtection gives its prot and bounds. Bytes written through RW
    read back through RX and R. On x86-64, `mov eax, 42; ret` written through RW runs through RX and returns 42;
  - map errors (3 EACCES, 2 EINVAL, 2 EBADF, address untouched), and an occupied hint maps at or above it;
  - lifetimes: munmap of the RX view gives OK, the range is gone and so is its memfd mapping. The four handles are closed
    through the four entry points, after which map and alias give EBADF. The other views still show the bytes; munmap OK.

**Risks.**
- The error answers and the budget are AnyPS5's, unmeasured on a console (`TODO(verify)` in the code).
- Handle numbers start at 0x40000; a title that assumes small descriptor numbers would notice.
- Not ported (held, below): `mmap` of a JIT handle and `dup`/`dup2` of one.
- With the switch on, every guest close first looks the handle up in the JIT table: below 0x40000 there is no lock;
  above it, one map lookup.
- A view's private-memory file range (offset = address) stays a hole under the overlay. BC5's private sync lists the
  range (type 5, name `bc5-jit`) but finds no data there. The GPU would see that hole, not the area: JIT code is
  CPU-only, so this is a risk only for a title that would point the GPU at JIT memory.
- The memfd is created without `MFD_EXEC`, like the unit's own two memfds. A host with `vm.memfd_noexec=2` would refuse
  it (create gives ENOMEM).

## R1 rows `excluded-provenance`, libkernel / libkernel_sys (exp 0405 `raw/r1-verdicts/A.tsv`)

| Row | R1 note (quoted) | Upstream source note | Lives in | Verdict |
|---|---|---|---|---|
| `520a8249a` libkernel | "request layout from firmware 13.42 library; libSceSysUtil not hosted, sceKernelSendNotificationRequest unregistered" | `docs/dev/debt/libSceSysUtil.md`: "follows @BunnyFl's firmware 13.42 run … under an emulator … not on a console"; `libkernel.md`: the library "only writes the request to a notification descriptor … and returns 0 or `0x80020000 \| errno`" | libKernel.cpp (registration) | **ported** (decision 1, a firmware run): `notify` |
| `cd341b465` libkernel_sys | "nine unnamed exports return firmware 13.42 library values (disassembly)" | "read from disassembly to the return, not measured on a console" (names the firmware's `libkernel_sys.sprx` and quotes the instructions, without addresses) | no libkernel_sys library is hosted (`runtimeLinker.cpp:2538` skips the module) | **held**: not in these files; provenance "disassembly", left to the coordinator |
| `8794fec07` libkernel_sys | "AMM mapper calls follow firmware 13.42 libkernel_sys disassembly" | "read from disassembly and not measured on a console" | AMM is in `libAmpr.cpp` / `bc5LleAgc.cpp` | **held**: not in these files; disassembly |
| `004b47eda` libkernel_sys | "128-bit limit and misspelled export GST42pfUfMc from firmware 13.42 disassembly" | "read from disassembly and not measured on a console" | `bc5LleAgc.cpp:10038-10119` (`TitleWorkaroundIsEnabled`, `1yca4VvfcNA`) | **held**: not in these files; disassembly |

**`notify` (`KYTY_BC5_FW_KERNEL`): sceKernelSendNotificationRequest. Ported.**

- **Source.** AnyPS5 `4f41f4c37` commit `520a8249a` (GPL-2.0-only):
  - `docs/dev/debt/libkernel.md` and `libSceSysUtil.md`, after @BunnyFl's run of firmware 13.42 under an emulator (AnyPS5
    pull request 9081, comment 6418015178);
  - AnyPS5's function, `core/libs/prx/libkernel/System/src/Notification.cpp:38-87`, for comparison.
- **Behaviour ported** (the run's part only):
  - the library writes the request to a notification device and returns 0 or `0x80020000 | errno`;
  - the system-text request is 0xc30 bytes, kind 5 in its first int32 and the text at +0x2d.
- **What ours does.** There is no device here, so the request is taken (returns 0). The text of a kind-5 0xc30-byte
  request goes to the log; other requests get a one-line log entry.
- **Not ported.** AnyPS5's refusals of other kinds, sizes, devices and flags: its note says they are its own, not the
  firmware's. Its kind-0 text layout comes from another commit, `d70d7ca26`, whose provenance is not in the verdicts.
- **TODO(verify).** NULL gives EFAULT. That is an inference from "0x80020000 | errno", not a measurement.
- **Change.**
  - `libKernel.cpp`: switch `Bc5FwKernelItems`/`Bc5FwKernelOn` (1976-1998), function 2010-2034.
  - Registration `zl7hupSO0C0` (exp 0327's calculator; shadPS4 aerolib agrees) in `InitLibKernel_1`, 3996-3998.
- **Test (case 8).** On: registered (NID and key), kind 5, kind 0 and a 16-byte request return 0, NULL gives EFAULT.
  Off: not registered (today's loader stub answers).

## Held, with sizes

- **`sceKernelJitGetSharedMemoryInfo` (`9yxlvURJU6U`).** AnyPS5 has it only as a libkernel_sys stub that reports
  "not implemented" and returns 0 (`libkernel_sys/Export.Discovery.cpp:1352-1355`, `(void)`). There is no behaviour to
  port. S, if a 0 stub is wanted.
- **`mmap` of a JIT handle.** AnyPS5 maps the object as a regular file, `PosixMemory.cpp`. Our mmap path for
  descriptors would need it. S-M.
- **`dup`/`dup2` of a JIT handle.** AnyPS5 `File/src/Stdio.cpp:940, 984, 1002`. Today it gives EBADF through the file
  system (`fileSystem.cpp`, not mine). S.
- The three libkernel_sys rows above.

## The CPU test `jit0405.cpp`

- **Setup:** core, threads, config (silent), log and memory, as `mem0405.cpp` does. Then `Libs::InitAll` into a
  `Loader::SymbolDatabase`, as `npgate0401.cpp` does, with a setup check that `vSMAm3cxYTY` (sceKernelMprotect)
  resolves.
- **Output:**
  - one line per case, `jit0405: case N <name> [<switch> on|off]: ok|FAIL (…)`;
  - then `jit0405: on 8 of 8; end` (both switches on), `jit0405: off 3 of 3; end` (both off or unset; cases 1, 2 and
    8), or `jit0405: mixed <switch on> N of N; end` (JIT only: 8 cases; FW only: 3).
  - Exit 0 only after the end line. A 60 s watchdog gives a FAIL line and exit 3; an argument that disagrees with the
    switches exits 2.
- **Build:** `build0401.py --gate jit0405.cpp <out> --like src/kernel/memory.cpp`, linked with every emulator object but
  main.cpp.o, with the private `memory.cpp.o` **and** `libKernel.cpp.o` (both from mkjit0405.py) in place of the shared
  ones.
- **Runs**, in a fresh directory:
  - `KYTY_BC5_JIT_SHM=1 KYTY_BC5_FW_KERNEL=1 jit0405 on`;
  - both `=0`, `jit0405 off`;
  - both unset, `jit0405 off`.

## Verified on the laptop (no box access)

- **The script.**
  - `mkjit0405.py e6/e5tree <out>` prints `src/kernel/memory.cpp ee24c888f976cc125502cf3a31006349` and
    `src/libs/libKernel.cpp 0a0d46657d8088b72a9ba67e2fbcc310`.
  - Run on its own output it refuses ("has the edit already", rc 1); a changed input stops on the md5.
  - Built in: the NID checks, block and edit balance, ASCII, LF only, and the undo check (new to old, then the block
    removed, gives the input byte for byte).
- **`diff`.**
  - memory.cpp: one insertion (4245-4468).
  - libKernel.cpp: the block, two appended registration groups, and four replaced lines. Each replaced line is a close
    registration, now inside if/else with the old line in the else.
- **Syntax.** Visual Studio 18's clang++ (msvc target), `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`. Setup: e5's
  stand-ins (`lib0405chk/stub`), fmt from `refs/Inori_GPCS4`, magic_enum from `refs/InoriRus_Kyty`, Vulkan and VMA
  headers from the local Vulkan SDK 1.4.341.1, `-D_CRT_*`. Script: `scratchpad/jitchk/chk.sh`.
  - memory.cpp output: clean. The input is clean too.
  - libKernel.cpp output: one error, the same as the input's, in today's fcntl code (`__builtin_sysv_va_start` does not
    exist for the msvc target; input line 2340, output 2454). Nothing else.
  - jit0405.cpp: clean.
  - **Linux branches:** the memory block was cut out into a harness (`jitchk/mklinux.py`) with `KYTY_PLATFORM` Linux
    and stand-ins for the names around it and the POSIX calls. It is clean, also with
    `-Wshadow -Wconversion -Wsign-conversion`. A negative control (an unused variable) is caught.
- **Not checked:** GCC/Linux clang on the box, the real Linux headers, the link, and running the test. The box build is
  the first real compile and run.

## Files

| File | md5 |
|---|---|
| `mkjit0405.py` (new) | `7cea87202c3db4bfb8b8233c39b1d1f7` |
| `jit0405.cpp` (new) | `3c604947dffecdd4071bbbe223a55236` |
| `jit0405-notes.md` (new) | this file |
| in: `src/kernel/memory.cpp` (e5's unit) | `95d9ca880d01db26d51f0ecabcdfa7e1` |
| out: `src/kernel/memory.cpp` | `ee24c888f976cc125502cf3a31006349` |
| in: `src/libs/libKernel.cpp` (e5's unit) | `b353287342a8eb82305a4592a4021e3d` |
| out: `src/libs/libKernel.cpp` | `0a0d46657d8088b72a9ba67e2fbcc310` |
| read only: `src/kernel/memoryAddressSpace.inc` | `44586b1ee0e7edf12a0cd293ff9c141f` |
| read only: `src/kernel/memory.h` | `8c25cc1f4db620c177adb04e8ee17452` |
| read only: `src/libs/errno.h` | `024847d05a02f78aec1c23a467bdd0cf` |
| read only: `src/libs/libs.h` | `30ad932ad5b56b0ca54dbee18e6997a6` |
| read only: `src/loader/symbolDatabase.h` | `b0e0ccdaab9d96c1d7e9fe93dfd64102` |
