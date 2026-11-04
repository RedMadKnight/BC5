# fs0405: file system ports of exp 0405 (BC5 exp 0401 series e5, tag `fs`)

Files: `mkfs0405.py` (the edit), `fs0405.cpp` (the CPU test), this note. Units: `src/kernel/fileSystem.cpp` and
`src/libs/libKernel.cpp` (registrations only). No header is edited. Nothing changes what is submitted to the GPU.

## Switches and their lines

| Switch | Unit | Items | Read | stderr line (once) |
|---|---|---|---|---|
| `KYTY_BC5_FS_FIXES` | fileSystem.cpp | `kk04 sk04 blksize nametoolong kk10 sk05` | at the FileSystem subsystem's init | `[bc5] exp 0405: fs fixes on (items: kk04 sk04 blksize nametoolong kk10 sk05)` / `[bc5] exp 0405: fs fixes off` |
| `KYTY_BC5_POSIX_RET_FIXES` | libKernel.cpp | `unlink munmap mprotect trywrlock schedparam once` | when libkernel's tables are built (`Libs::InitLibKernel_1`) | `[bc5] exp 0405: posix return fixes on (items: ...)` / `... off` |

Grammar (e4's `KYTY_BC5_AUDIO_FIXES`): unset, empty or `0` is off; a comma list of item names turns on only those; any
other value (`1`, `on`, a list naming no known item) turns all items on. Off means today's code path in every edited
function (the old code is kept, under an `if`/`else` on the switch) and today's registrations.

**`KYTY_BC5_POSIX_RET_FIXES` is a registration switch.** It is read once, when the library's symbol table is built at
start. Changing the variable later has no effect until the next start. With it off the table is byte-for-byte today's
(the same functions under the same NIDs).

## Items

### 1. R2 KK04 (+SK02): `sceKernelRename` of open files and directories, item `kk04`: **ported**

- **Today:** `KernelRename` EXITs when either path has an open descriptor (input `fileSystem.cpp:1456-1457`). A
  directory gets ENOENT (`:1459`, file-only). A rename onto the same file deletes it, then answers EIO.
- **Sources:**
  - KytyPS5 dfec14a `src/kernel/fileSystem.cpp:1398-1430` (GPL-2.0): no open-file check.
  - sharpemu 1811cef "[Kernel] Allow renaming and unlinking open guest files", at 514d766
    `SharpEmu.Libs/Kernel/KernelFileExtendedExports.cs:330-380` (GPL-2.0-or-later): `Directory.Move`, and `File.Move`
    with overwrite.
  - Adapted, no code taken.
- **Change (output `fileSystem.cpp`):**
  - `Bc5RenameFixed` (1754-1796) is called from `KernelRename` (1814-1816) before today's EXITs.
  - A file takes today's steps. Its target's parent is made, and an existing target file is replaced. A directory
    target is EISDIR (today EIO).
  - A directory goes through the host's `rename(2)`. The target may be missing or an empty directory. A non-empty
    directory gives ENOTEMPTY, a file gives ENOTDIR, another host file system gives EXDEV.
  - A rename onto the same file (`std::filesystem::equivalent`) is OK and does nothing.
  - **Open descriptors follow the rename** (`FileDescriptors::Bc5Rename`, 421-452). The source's descriptors, and
    those of anything under a renamed directory, take the new host name, so `fsync` and `fchmod` reach the right path.
    A replaced target's descriptors keep their file and lose its host name (`Bc5Forget`, 404-416). Otherwise a later
    `truncate`/`unlink` by name would hit the old open file.
  - **`KernelUnlink`** (1726-1741), switch on:
    - It unlinks the host name, which is what `SysFileUnlink` does on Linux. Today's `open_file->f.Unlink()` would
      delete the name the file had when it was opened, wrong after a rename.
    - The unlinked file's descriptors lose the name, the same rule as a replaced target.
- **Test:** cases 1-6.
  - On only: 1 (an open source; then a rename, unlink of the new name, and a write while open) and 2 (an open target,
    then a truncate by name). Off, both are "not run", because today's code EXITs.
  - Both settings: 3 (a directory: OK / ENOENT), 4 (onto itself: OK and kept / EIO and deleted), 5 (closed, missing,
    and a file onto a directory: EISDIR / EIO), 6 (unlink of an open file, then a new file of that name truncated by
    name).
  - Off, case 6 shows today's bug: the truncate hits the unlinked open file, not the new one.
- **Risks:**
  - A descriptor whose file was replaced or unlinked has an empty host name. `KernelFsync` on it then answers ENOENT
    (it reopens by name; today it reopens the stale name and also fails, or syncs a different file). Its `fchmod`
    fails too. TODO: an fd-based fsync.
  - Linux-only reasoning: on Windows an open file cannot be unlinked by name. BC5 is Linux-only.

### 2. R2 SK04 (+KK09): `KernelOpen` without EXITs, item `sk04`: **ported**

- **Today:**
  - `O_ACCMODE` 3 EXITs (input `:469`).
  - `O_DIRECTORY` with write access, `O_TRUNC` or `O_CREAT` EXITs (`:472-473`), and so does an existing directory
    opened that way (`:532-533`).
  - `O_TRUNC|O_RDONLY` returns EACCES without freeing the descriptor (`:513-515`).
- **Sources:**
  - sharpemu 956da76, at 514d766 `KernelMemoryCompatExports.cs:1512-1530` and `4827-4839` (GPL-2.0-or-later).
  - KytyPS5 dfec14a `src/kernel/fileSystem.cpp:495-498` (GPL-2.0), the descriptor freed.
  - The error values are FreeBSD's: `kern_openat` gives EINVAL for `O_ACCMODE`; `vn_open_cred` and `vn_open_vnode`
    give EEXIST, then EISDIR. The `O_ACCMODE` check also appears in obhq/obliteration 2a53d5c
    `legacy/src/fs/mod.rs:393-400` (MIT/Apache-2.0; fact only, no code).
  - sharpemu answers INVALID_ARGUMENT for a directory and maps 3 to read-write. We follow FreeBSD.
  - TODO(verify) on a console.
- **Change:**
  - `O_ACCMODE` 3 is EINVAL, before a descriptor is made (732-735).
  - The `O_DIRECTORY` EXITs are skipped with the switch on (740-743). The open reaches the directory branch, where a
    directory opened for writing, `O_TRUNC` or `O_CREAT` gives EISDIR, or EEXIST with `O_CREAT|O_EXCL`, and the
    descriptor is freed (805-814). A file named with `O_DIRECTORY` gives ENOTDIR, a missing one ENOENT (today's code).
  - The EACCES path frees its descriptor (784-786).
  - `O_TRUNC|O_RDONLY` stays EACCES, as today and as KytyPS5 (FreeBSD would truncate; not this item).
- **Test:** cases 7-10.
  - 7 (EINVAL, no descriptor used) and 8 (nine refused opens, then the same lowest free descriptor) run on only. Off
    they are "not run", because today's code EXITs.
  - 9 (a directory opened for reading) runs in both settings.
  - 10 runs in both settings: 100 × `O_TRUNC|O_RDONLY`, all EACCES. The next descriptor is the same with the switch
    on, 100 higher with it off (today's leak).
- **Risks:**
  - A title that relied on the EXIT is not a concern.
  - A title that opens a directory `O_RDWR` and ignores the error now continues: correct behaviour.

### 3. R1 #9 + R2 SK06 + R3 M15: return conventions, `KYTY_BC5_POSIX_RET_FIXES`: **ported**

- **Pattern:** the file's posix wrappers (`POSIX_CALL` / `POSIX_PTHREAD_CALL`, `libs/errno.h`). These are the same as
  `Posix::mkdir` (input `libKernel.cpp:1999`) and exp 0336's `pthread_rwlock_tryrdlock` (`pthread.cpp:4734`), which R2
  calls R34.
- **New static wrappers** in libKernel.cpp's `Posix` namespace (output 2387-2525) call today's functions and only
  translate the result:

| Item | NID (name, checked by hash) | Today | On |
|---|---|---|---|
| `unlink` | `VAzswvTOCzI` unlink (libkernel table, out 3826-3830) | `FileSystem::KernelUnlink`: SCE codes | `Bc5PosixUnlink`: -1, errno |
| `munmap` | `UqDGjXA5yUM` munmap (Posix table, 2623-2627) | `Memory::KernelMunmap` | `Bc5PosixMunmap`: -1, errno |
| `mprotect` | `YQOfxL4QfeU` mprotect (2618-2622) | `Memory::KernelMprotect` | `Bc5PosixMprotect`: -1, errno |
| `trywrlock` | `XhWHn6P5R7U` pthread_rwlock_trywrlock (2608-2612) | `PthreadRwlockTrywrlock`: 0x80020010 | `Bc5PosixRwlockTrywrlock`: errno numbers (16) |
| `schedparam` | `P41kTWUS3EI` scePthreadGetschedparam, `oIRFTjoILbg` scePthreadSetschedparam (2560-2570) | `Posix::pthread_get/setschedparam`: errno numbers (22) | SCE codes (0x80020016) |
| `once` | `14bOACANTBo` scePthreadOnce (libkernel table, 3813-3817) | `Posix::pthread_once`: 22 | SCE codes |

- **Sources:**
  - AnyPS5 4f41f4c37 `core/libs/prx/libkernel/File/src/Stdio.cpp:1227` (GPL-2.0-only), for unlink.
  - shadPS4 60c42b9 `src/core/libraries/kernel/memory.cpp:421-428, 851-859` (GPL-2.0-or-later; checked), for
    `posix_mprotect` / `posix_munmap`.
  - sharpemu 0c467e8 (posix trywrlock) and bb3318a (`PosixFailure`, `KernelMemoryCompatExports.cs:1684-1700` @
    514d766).
- **The sce wrappers' mapping:** they map an errno number back to 0x80020000 + n. That is `KernelToPosix`'s inverse on
  its range, so every code these functions return round-trips exactly. The `Pthread` struct is private to
  `pthread.cpp`, so the spec's "bodies minus `KernelToPosix`" could not be copied without touching that file. Wrapping
  today's posix function gives the same codes.
- **NIDs:** `mkfs0405.py` checks every NID it registers against its name (exp 0327's calculator, self-checked on
  strcmp/strncmp/strcpy_s; lesson R32). The names are as in shadPS4's `aerolib.inl`.
- **Ownership:**
  - `pthread.cpp` and `memory.cpp` were not touched.
  - The wrappers are `static`, with `Bc5` names, so a `Posix::pthread_rwlock_trywrlock` that another agent might add
    cannot clash.
  - The munmap/mprotect cases rely on today's early EINVAL in `KernelMunmap` (len 0) and `KernelMprotect` (no known
    protection bit). If the memory agent's e5 edit changes those checks, cases 19-20 need a look.
- **Test:**
  - Case 17 looks up the seven registrations from `InitLibKernel_1` in a SymbolDatabase, each by its exact table key.
    On, it expects the wrapper; off, today's function.
  - Cases 18-23 call through the registered pointers: unlink of a file and of a missing one; `munmap(0x10000, 0)`;
    `mprotect` len 0 and prot 0x100; trywrlock free, held by self (EDEADLK) and held by another thread (EBUSY); get/set
    schedparam with NULL and self; once with NULL, then twice (the routine runs once).
- **Risk:** a title that read today's SCE values from these posix NIDs as if they were -1/errno already misread them.
  No title is known to depend on the wrong convention.

### 4. R1 #12: directory `st_blksize`, item `blksize`: **ported**

- AnyPS5 da7581eec `core/libs/prx/libkernel/File/src/NativeStat.cpp:224` @ 4f41f4c37 (GPL-2.0-only). The commit cites a
  PS4 Pro 10.71 measurement, not a PS5. TODO(verify) on a PS5.
- **Change:** `KernelStat` (1265) and `KernelFstat` (1343) report 0x10000 for a directory with the switch on; files and
  special files keep 512.
- **Test:** case 11, stat and fstat of a directory (0x10000 / 512) and of a file (512 both).

### 5. R1 #13: ENAMETOOLONG, item `nametoolong`: **ported**

- AnyPS5 2de34f87b `core/libs/prx/libc/src/General.cpp:386-388` @ 4f41f4c37 (GPL-2.0-only); FreeBSD MAXPATHLEN 1024 and
  NAME_MAX 255.
- **The rule:** CheckGuestPath's length rule (exp 0327, input `:1111`). The relative-path and EFAULT parts are not
  used.
- **Change:**
  - `Bc5PathTooLong` (247-260) runs in `KernelOpen` (698), `KernelStat` (1236), `KernelUnlink` (1706), `KernelRename`
    for both paths (1805), `KernelRmdir` (2016), and `KernelMkdir` and `KernelCheckReachability` (1977, 2042).
  - In `KernelMkdir` and `KernelCheckReachability` it replaces today's "any path over 255 bytes" refusal.
  - AnyPS5 answers a long component after a missing directory with ENOENT. We answer ENAMETOOLONG (the simpler rule
    of `CheckGuestPath`). TODO(verify).
- **Test:** cases 12-14.
  - 12 and 13 run all seven functions on 1024 bytes and on a 256-byte component. Case 12 also renames a file to the
    1024-byte name; off, today's code moves it there.
  - 14 checks 1023 bytes (ENOENT), a 255-byte component (mkdir OK on), and a 297-byte path of short components (mkdir
    OK on). It also runs CheckReachability on a 292-byte path (OK on).
  - Off, every case expects today's ENOENT, and ENAMETOOLONG for mkdir and CheckReachability.

### 6. Extras

- **R2 KK10, item `kk10`: ported.**
  - KytyPS5 dfec14a `src/kernel/fileSystem.cpp:722, 940` (GPL-2.0).
  - `KernelWrite` (997) and `KernelPwrite` (1126) answer EBADF for a descriptor that is not open for writing. This is
    checked before the directory check, as FreeBSD's `fget_write` does. A read-only directory descriptor gets EBADF
    (today EISDIR).
  - Case 15. Off, today's code writes 0 bytes to a read-only file and answers EISDIR for a directory.
- **R2 SK05 (+KK35), item `sk05`: ported.**
  - sharpemu 9ff60ab and e01092a, at 514d766 `KernelMemoryCompatExports.cs:5070-5110, 5176-5203` (GPL-2.0-or-later).
  - `Bc5NormalizeGuestPath` (264-299) runs at the top of `GetRealFilename` and `GetRealDirectory` (561-588, 621-640),
    under the mount table's lock. "." is dropped, ".." pops a level (never above "/"), "//" folds, and a trailing
    "/", "/." or "/.." keeps the directory form. The longest matching mount point wins (`Bc5LongestMount`). A mount
    point named without its '/' maps to the mount itself (KK35: `open("/app0", 0)`).
  - Differences from sharpemu: the whole path is normalised, so `/app0/..` is `/`, which is under no mount (ENOENT)
    rather than clamped. The ".." walk is lexical: `/app0/x/../f` resolves even when x is missing, where FreeBSD's
    namei would say ENOENT. TODO(verify).
  - Case 16. Off, today's escape `/temp0/../outside.txt` reaches a file in this run's own work directory. That is by
    design: nothing outside it is touched.
  - **Risk:** M. Every path goes through it when on. Relative paths are unchanged.
- **Held: R2 KK21** (sceKernelPreadv/Writev/Pwritev). This is a port of about 180 lines plus a `readable` flag (R2:
  "borderline M"), not a registration, so it was held for time.
- **Held for time** (in my files, e4-now in R2, not in my brief's list): R2 SK13 (+KK22), alias registrations onto
  existing fileSystem.cpp functions; KK11 (`stat("/")` as a directory); KK12 (`_write` to fd 0-2); KK16 (ENOSPC/EFBIG
  mapping); KK18 (`S_IFCHR` for devices); KK36 (`O_CLOEXEC` at open). SK13's `pthread_getthreadid_np` alias belongs to
  the pthread.cpp owner.

## The CPU test (`fs0405.cpp`)

- **Build:** `build0401.py ... src/kernel/fileSystem.cpp=<out> src/libs/libKernel.cpp=<out> --gate fs0405.cpp <bin>
  --like src/kernel/fileSystem.cpp`.
- **Runs:** `KYTY_BC5_FS_FIXES=1 KYTY_BC5_POSIX_RET_FIXES=1`, then both `=0`, then both unset.
- **Expected end lines:** `fs0405: on 23 of 23; end` (on); `fs0405: off 19 of 19; end` (off and unset; cases 1, 2,
  7 and 8 are "not run" lines, because today's code EXITs there).
  - A comma list prints `mixed N of N`.
  - Exit 0 only after the end line.
  - A watchdog stops a hang after 60 s (exit 3).
- **Isolation:**
  - It works in a fresh `fs0405-work-<pid>` under the current directory and refuses a path containing `bc5-data`.
  - It mounts only that directory's `mnt`, `mnt2` and `nested` as `/temp0`, `/temp1` and `/temp0/sub`, and removes
    the directory at the end.
  - No game, save, GPU, window, sound or network is used.
- **What it avoids:** it makes no reads through descriptors, because `KernelRead`/`KernelPread` invalidate the GPU view
  (`Memory::InvalidateMemory` needs the graphics side). Data are checked on the host and through `fstat` and writes.
- **Subsystems:** Threads, Pthread and FileSystem are initialised on a helper thread (pth0401's way). Logging is off.

## Verified on the laptop

- `mkfs0405.py e5/e4tree <out>` prints the two output md5s below. Both input md5s are asserted. The NID check passes.
- **Refusals:**
  - Run on its own output, it stops on the input md5.
  - The edit functions called directly on their own output stop with "has the edit already".
- **Revert check:** undoing every replacement in reverse order gives both inputs back byte for byte (scratch
  `verify_fs.py`).
- **Balance:** braces, parentheses and brackets balance outside comments and literals in both outputs and in the
  test.
- **Encoding:** the inserted text is ASCII (non-ASCII byte counts unchanged: 6 and 18).
- **Syntax check** (`--target=x86_64-pc-windows-msvc -fsyntax-only -std=c++20 -Wall -Wextra -Werror`): Visual Studio
  18's clang++, in the tree's Windows configuration. Stand-in `cmake_config.h` and `unistd.h` (as the other e5
  agents'), a stand-in `sched.h`, fmt from `refs/Inori_GPCS4` and magic_enum from `refs/InoriRus_Kyty` as `-isystem`,
  `-D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS`.
  - **fileSystem.cpp** (input and output): clean.
  - **libKernel.cpp:** the output has exactly the input's errors, all in today's code: `__builtin_sysv_va_*` in fcntl
    at 2339-2342, which are Windows-target-only. With those mapped to the plain builtins, one remains in both (`va_start
    used in System V ABI function`). The new code adds none.
  - **fs0405.cpp:** clean, also with `-Wshadow` (plus `-Wno-deprecated-declarations` for Windows' `getpid`).
- **Not checked:**
  - GCC on the box.
  - The Linux branches.
  - The link.
  - Running the test. Windows' rename and unlink semantics for open files differ, so no stand-in run was attempted.

## Files

| File | md5 |
|---|---|
| `mkfs0405.py` (new) | `693201423f170d992126e1f5c25fd6d4` |
| `fs0405.cpp` (new) | `3f6363c62f5ad1a18af8a197c8f08c52` |
| `fs0405-notes.md` (new) | this file |
| in: `src/kernel/fileSystem.cpp` (base tree) | `f1b5f5288faddd78deff2dbd1b613e1f` |
| out: `src/kernel/fileSystem.cpp` | `a7201a1ab20dc60d876ad64f0dd4d086` |
| in: `src/libs/libKernel.cpp` (base tree) | `3bf94a6168d176d591730bac33dff5b1` |
| out: `src/libs/libKernel.cpp` | `b353287342a8eb82305a4592a4021e3d` |
