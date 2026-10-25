# 0327 — the second title's twelve missing imports, implemented as the console behaves

**Question.** On 2026-10-25 the shared normal build 5dd77a82 crashed twice at the same game moment (~90 s and ~120 s
after the start) with an access violation in the title's own code on one path (eboot+0x3af96ce → 0x3af9f84 →
0x3d75a31, an object release with a corrupt vtable / refcount); the pre-0323 build crashed at exp 0299's site (read
0xc at eboot+0x3d7eca0, ~4 min in). The crash dump's "recent stubbed import" list — the last twelve stubs created at
link time — resolves to twelve NIDs the host answers with a return-0 stub (the top session's NID work, verified on
known pairs):

| NID | library | name | f266548 |
|---|---|---|---|
| tB59hFLH3SA | LibcInternal | sceLibcInternalForceTlsDestructor | missing |
| OQ-dzhlnM28 | LibcInternal | sceLibcInternalFinalizeTls | missing |
| hHlZQUnlxSM | libkernel | getrusage | missing |
| 0Cq8ipKr9n0 | libkernel | sceKernelUtimes | missing |
| WlyEA-sLDf0 | libkernel | sceKernelTruncate | missing (upstream has it) |
| fgIsQ10xYVA | libkernel | sceKernelChmod | missing |
| UtszJWHrDcA | libkernel | sceKernelFchmod | missing |
| XD3mDeybCnk | libkernel | scePthreadRwlockTryrdlock | the function exists, registered under SFxTMOfuCkE only |
| adh--6nIqTk | libkernel | scePthreadRwlockTimedwrlock | the function exists, not registered |
| iPtZRWICjrM | libkernel | scePthreadRwlockTimedrdlock | the function exists, not registered |
| dFym5b41JLU | libkernel | sceKernelSyncOnAddressWait8 | missing |
| XgVs4jRehcY | libkernel | sceKernelSyncOnAddressWait16 | missing |

A stub returning 0 lets a waiter run on before its condition holds (the two SyncOnAddress waits, the timed rwlocks —
the prime suspects for a release of an object another thread still owns), tells a title its file operation succeeded
when nothing happened, and skips the TLS destructors a module's unloading relies on. The maintainer's word: "spróbuj
ich zrekonstruować … I oczywiście użyć tak jak powinny być użyte a nie robić własne zaślepki w kodzie". Does the title
pass that moment with the twelve implemented?

**Sources used (as the maintainer asked, not only KytyPlus).** The tree itself, f266548 + patch 0001 as the box has it
(reconstructed offline from `refs/Coder787-source_KytyPlus` at f266548 with raw blobs, the patch from the repo's git
object; `bc5LleAgc.cpp` md5 5bccbb80 = the box's). Upstream KytyPlus HEAD (GPL-2.0): `KernelTruncate`
(src/kernel/fileSystem.cpp:1227) — ported onto this tree's path resolution (`GetRealFilename`, no `ResolvePath`), its
host-error mapping kept; the timed rwlocks are registered there on a reworked cooperative rwlock — not ported, this
tree's own `PthreadRwlockTimedrdlock` / `Timedwrlock` are used. AnyPS5 (GPL-2.0): the semantics of `Wait8` / `Wait16`
(a wait keyed by the exact address, any alignment accepted by the wake), `getrusage` (the FreeBSD layout, `who` −1 / 0 /
1, EINVAL / EFAULT by errno), `ForceTlsDestructor(handle)` (the destructors registered from the module `handle`, found
through the DSO symbol they were registered with, run and removed; passes until none is found), the thread-destructor
list per thread; nothing copied. shadPS4 (GPL-2.0-or-later): `sceKernelTruncate` / `Chmod` / `Fchmod` / `Utimes` as
posix calls with the sce error mapping, the `utimes` `tv_usec` range check (EINVAL). PS5PCEM (GPL-3.0, semantics only):
`finalizeTls` and `forceTlsDestructor` both run the thread's destructors. FreeBSD's `struct rusage` for the layout.

**Setup.** `patch0327.py` (7 files, 423 lines; anchors verified offline 23/23 on the reconstructed tree, braces
balanced — no compiler on the laptop, the first compile is the box's):
- `src/kernel/syncOnAddress.{h,cpp}`: `Wait8` / `Wait16` through the same `WaitImpl`; on Linux a narrow wait sleeps on
  the futex of its containing aligned 32-bit word with that word's current value as the expected one (the futex
  compares 32 bits), re-checking its own byte / half-word before and after; a wake goes to the aligned word
  (`FutexWordOf`), so a byte address wakes its waiters; `IsValidWakeAddress` accepts any non-null address as the console
  does. The portable path (non-Linux) keys waiters by the exact address, unchanged.
- `src/libs/libKernel.cpp`: the two `Posix::KernelSyncOnAddressWait8/16` wrappers (with the tree's "experimental"
  one-time log, the signal poll as the others) and their NIDs; the three rwlock NIDs on the existing functions;
  `getrusage` in the posix set (`KernelRusage`, 144 bytes, static_assert; host `getrusage(RUSAGE_SELF / RUSAGE_THREAD)`
  into it; −1 with errno EINVAL / EFAULT); the four file NIDs.
- `src/kernel/fileSystem.{h,cpp}`: `KernelTruncate`, `KernelChmod`, `KernelFchmod`, `KernelUtimes`: the console's checks
  first (EFAULT null path, EINVAL relative path / negative length / `tv_usec` out of range, ENAMETOOLONG over 255 per
  component or 1023 in all, EROFS on `/app0`, `/system`, `/hostapp`), the mount points resolve the host file (ENOENT,
  EISDIR for a directory where a file is needed), then the host operation: an open file is truncated through its own
  handle, else `std::filesystem::resize_file`; permissions through `std::filesystem::permissions` with the owner's read
  and write kept (the host must still open the title's files); times through `utimensat` (`UTIME_NOW` for a null
  `times`); host errors mapped as upstream maps them (`KernelErrorFromHost`).
- `src/libs/libC.cpp`: the thread_atexit record keeps the DSO handle symbol (`__cxa_thread_atexit`'s third argument,
  dropped before); `LibcInternalForceTlsDestructor(int handle)` runs and removes, on the calling thread, the
  destructors whose DSO symbol lies in the program with `unique_id == handle` (the runtime linker's
  `FindProgramByAddr`), last registered first; `LibcInternalFinalizeTls()` runs them all (`RunThreadAtexitDestructors`,
  as at thread exit). Both registered in `InitLibcInternal_1`.
- `src/loader/runtimeLinker.cpp`: at link time one `RawLog` line per stubbed import on stderr (`[bc5] stubbed import
  #n: NID[lib][module] (program …)`) — the title's complete missing list, no CRT, not dropped by the silent console —
  and one at a stub's first call (`[bc5] stubbed import called: …`), beside the tree's LOGF lines.
- `SyncOnAddressTests.cpp` (after upstream's tests/SyncOnAddressTests.cpp, GPL-2.0, the same Check style): invalid
  addresses (null, misaligned 32/16, a byte-address wake accepted), immediate return when the value differs (all four
  widths), timeouts (8/16), a waiter woken by a store + wake at each width, a byte inside a word with its neighbours
  untouched, four 16-bit waiters woken together. `build0327.sh` builds the six units with the shared flags (the patched
  headers first on the include path), relinks against the shared objects (5dd77a82) and the shared archive (825ae1d1,
  exp 0290's refusal), then builds and runs the tests (linked with the shared common objects, or with every shared
  object but main's if the minimal link fails); a failing test ends the script with the emulator built and the failure
  printed. `patch_0327.diff` (raw/) is the diff for the integration (D19).
- Not in scope: `sceKernelSyncOnAddressWakeAll` (abtYmeCAHw8) — not in the twelve; the tree does not register it either;
  if the title imports it the link-time list will say so (then: `Wake(address, INT_MAX)`).

**Run.** The build on the box (~2 min, CPU only, under its lock line), then the maintainer plays to the same moment on
a desktop shortcut of the private binary (the top session sets it up); the stderr of that play carries the link-time
stub list and the first calls. Readings: the moment passes → the twelve (or the waits among them) were it, and the
stub list says what else the title misses; the same crash → the twelve are not the cause (the stub list and the first
calls say whether any of them even ran before the crash), and the release path at eboot+0x3d75a31 is the next lead.

**Result — the build and the start check (2026-10-25).** `build0327.sh` on the box at 21:25:23–21:26:04: the patch
applied to the tree as on the laptop (`raw/patch.out`, 433 diff lines; `raw/patch_0327.diff` is the integration diff),
the six units compiled with the shared flags and the patched headers first, relinked against the shared objects 5dd77a82
and the shared archive 825ae1d1 (exp 0290's refusal): **kyty_emulator 1f7169a9**, first compile clean — 7 warnings, all
pre-existing (the portable path's unused functions in syncOnAddress.cpp, stringUtils' wstring_convert, a runtimeLinker
lambda), none in the new code. **SyncOnAddressTests: all checks passed** (`raw/tests.out`) — invalid addresses, the
immediate return at all four widths, the 8/16-bit timeouts, a waiter woken by a store and a wake at each width, a byte
inside a word with its neighbours untouched, four 16-bit waiters woken together. `start0327.sh` (the integrated launcher's
copy with the 0306 edits, RT off, private wd, live saves f00fc16b3f853e34 compared only): **120 s, boots and runs**, 0
crash / kernel / TIMEOUT lines, the lock released at 21:29:22 (`raw/S1-*`, `raw/start0327.out`). The diagnostics are
live: **197 imports stubbed at link** (`raw/S1-stub-list.txt`: NID[lib][module] per line — the title's complete missing
list; the twelve are no longer in it; mostly Np*, PlayGoDialog, PlayerInvitationDialog, NpCppWebApi, NpWebApi2, Http,
Coredump, Posix), **6 stubs called in the first 120 s** (`raw/S1-stub-calls.txt`): juWbTNM+8hw (Posix/libkernel),
kP2L8t3j-aM (VideoOutVrrStatus), w7Ipp9Xl7hg (VideoOut), 9030RnBDoh4 and 7aGTPfrqT9s (PngEnc), GTfJ64qFCPw (Acm) —
none of the twelve ran before the route's first two minutes, as expected (the crash moment is deeper in). The
maintainer's test on a desktop shortcut of the binary, with a log per start, decides the question: his play to the
same moment, and the log's "[bc5] stubbed import called" lines say which of the twelve ran before it.

**The six stubs called in the start check, resolved (the top session's NID calculator):** juWbTNM+8hw `fsync`,
kP2L8t3j-aM `sceVideoOutAddVrrStatusFlagsPrivilege`, w7Ipp9Xl7hg `sceVideoOutAllowOutputResolutionWqhdDetection`,
9030RnBDoh4 `scePngEncQueryMemorySize`, 7aGTPfrqT9s `scePngEncCreate`, GTfJ64qFCPw `sceAcmBatchJobPriority`.

**The whole link-time list resolved (offline; `raw/S1-stub-list-resolved.txt`, `nidcalc.pl`).** Method: the NID is the
base64 ("+-" alphabet, no padding) of the first 8 bytes of SHA1(name + 518d64a635ded8c1e6b039b1c3e55230) reversed, the
calculator verified on four known pairs; candidates were every `sce*` and posix identifier in `refs/` (28,007 names,
AnyPS5's `_nid_postfix` suffixes stripped) and every mangled C++ symbol there (90,488, mostly AnyPS5's
`libSceNpCppWebApi` exports); pcsx5's `assets/nid_db.txt` and the other projects' NID tables gave the same answers where
they had one. **186 of 197 resolved**; the 11 left are NpCppWebApi symbols without a candidate name (−0Vv7HKZaBM,
BY1jyWLZrcA, JiY4sfHkV34, LbhH9NeB93I, XUeWyaje50Q, XuVY56j7GM0, eVU3cXIJz0w, fIzsqjyD5oY, sRn6qePT54Q, xjVhrq2KPJA,
yl3T9brJay4). By library:

| library | count | what | class |
|---|---|---|---|
| NpCppWebApi | 147 (136 named) | `sce::Np::CppWebApi::Common::{IntrusivePtr, Vector, String, LibContext, initialize…}` (98), `SessionManager::V1` request/response classes (33), `TitleCloudStorage` (5) — the C++ online-session API: constructors, destructors, setters, iterators, `operator->` | **needs attention if reached**: a return-0 stub for a constructor or `operator->` leaves the object uninitialised or returns a null pointer, and the next use is an access violation in the title's own code — the crash signature of tonight (an object release with a corrupt vtable / refcount). Offline the title may never reach them; the first-call lines decide. AnyPS5 (GPL-2.0) implements exactly these (`core/libs/prx/libSceNpCppWebApi/Export.cpp`, intrusive pointers and vectors), portable. |
| PlayGoDialog | 6 | Initialize / Open / UpdateStatus / GetResult / Close / Terminate | harmless while the dialog is not opened (exp 0298 answers PlayGo itself); if opened, `GetResult` must fill its result (status finished, result OK) — cheap. |
| NpCommerce | 5 | the commerce dialog | harmless (store dialog; same note on `GetResult`). |
| Coredump | 5 | `sceCoredumpAttachMemoryRegion`, `GetStopInfoCpu`, `GetStopInfoGpu_Agc`, `SetUserDataType`, `WriteUserData` | harmless (the title's own crash-dump hooks). |
| PngEnc | 4 | `scePngEncQueryMemorySize`, `Create`, `Encode`, `Delete` | **needs a real implementation**: `Create` returning 0 without a handle and `Encode` returning 0 without output leave the title's screenshot / save-thumbnail path with garbage (called in the first 120 s: `QueryMemorySize`, `Create`). A PNG writer over the title's buffer (stb-style, or the host's); the SDK's API shape is in shadPS4's `libraries/png` (PS4). |
| NpWebApi2 | 4 | push-event context / filter / callbacks | harmless offline. |
| NpSessionSignaling | 3 | Deactivate / DestroyContext / Terminate | harmless offline. |
| PlayerInvitationDialog | 3 | GetResult / UpdateStatus / Terminate | harmless (same `GetResult` note). |
| VideoOut / VideoOutVrrStatus | 4 | `sceVideoOutAllowOutputResolutionWqhdDetection`, `AddVrrStatusFlagsPrivilege`, `VrrPegToFixedRate`, `VrrUnpegFromFixedRate` | harmless (VRR and WQHD negotiation; two called at start). |
| Posix | 4 | `sleep`, `fsync`, `fcntl`, `shutdown` | **needs a real implementation**: `sleep` returning at once instead of sleeping (a title loop spinning), `fcntl` returning 0 for every command (`F_GETFL` / `F_SETFL` on sockets and files — wrong flags silently), `fsync` (a no-op is acceptable for durability but should flush the host file); `shutdown` harmless offline. All four are short on the tree's own primitives (`KernelNanosleep`, the file table, `Common::File::Flush`). |
| libkernel | 4 | `rmdir`, `signal`, `sceKernelMlock`, `sceKernelInternalMemoryGetModuleSegmentInfo` | `rmdir`: registration only (`KernelRmdir` exists, this NID is missing) — **cheap**; `signal`: must return the previous handler and install the new one (the tree's sigaction path) — **needs a real implementation**; `sceKernelMlock`: harmless (0); `sceKernelInternalMemoryGetModuleSegmentInfo`: fills a segment-info struct the caller then reads — **needs a real implementation** (the runtime linker has the segments). |
| NpManager | 1 | `sceNpGetAccountLanguage2` | **cheap real implementation** (fill the language from the user settings; a 0 with an unfilled buffer can mis-localise). |
| NpEntitlementAccess | 1 | `AbortRequest` | harmless. |
| Http | 1 | `sceHttpReadData` | harmless offline (0 = nothing read). |
| Pad | 1 | `scePadGetAccessibilityControllerState` | **cheap**: fill "not an accessibility controller". |
| SaveData_native | 2 | `sceSaveDataCancel`, `sceSaveDataGetConvertProgress` | cheap: proper error codes (nothing to cancel, no conversion). |
| LibcInternalExt | 1 | `sceLibcInternalBacktraceForGame` | harmless (0). |
| Acm | 1 | `sceAcmBatchJobPriority` | harmless (called at start; a priority hint). |

So beyond the twelve: 147 online C++ symbols whose first-call lines will say whether the title touches them offline,
and about a dozen short real implementations (`sleep`, `fcntl`, `fsync`, `signal`, `rmdir`'s NID, the segment info,
the language, the pad state, the two save-data codes) plus one larger one (PngEnc). The rest are dialogs and online
services that a no-op serves, with `GetResult` the one call that must fill its struct if the dialog is ever opened.
