# 0326 — G5 attempt 3: the second title by hand after the ring-ordering integration

**Question.** Does the second title pass gate G5 (`docs/PHASES.md`: a 60-minute hand session on the default shared
build with no GPU hang, fault or machine-down, recorded with the kernel stream)? The setup is the one integrated an hour
before: exp 0323 (F388), the refusal in the shared archive, and `BC5_DIRECT_RING_DEPS=dcb` plus the compaction on in
the launchers.

**Setup.**
- The maintainer plays by hand from his own saves, RT off as saved (`RayTracing.PPSA03671=off`).
  - Try 1 and try 2: the desktop shortcut "BC5 emulator", normal build 5dd77a82, `play-pkg.sh` c0357628.
  - Try 3: a temporary shortcut "BC5 emulator (test: przed 0323)" with the build and launcher from before
    the integration (normal d02f4696 through `BC5_EMU`, `play-pkg.sh` bb51caf2, copies in `~/bc5-work/exp0326/`). It
    checks whether the crashes come from the integration.
- Recording: exp 0315's scripts renumbered (`stream0326.sh`, `sample0326.sh`), under the BOX-LOCK line
  "MAINTAINER PLAYING | G5 attempt 3, exp 0326". Saves: bb14b6dd35b644ff before, f00fc16b3f853e34 after
  (`raw/pre.txt`, `raw/post.txt`).
- Raw files: `raw/kernel-stream.txt`, `raw/journal-stream.txt.gz`, `raw/samples.txt`, and the crash extracts
  `raw/crash-*.txt`. The extracts keep the exception, registers, stack trace offsets and stub list. The code bytes and
  guest memory dumps stay in the full play logs on the box, `~/bc5-work/exp0326/play-try*.log`.

**Result.** Not a G5 pass. Four starts:

| start | build | end | what |
|---|---|---|---|
| try 1, 20:44:28 | 5dd77a82 | 20:46:29, exit 65 | access violation, read [0], at eboot.bin+0x3ba760d |
| try 2, 20:48:42 | 5dd77a82 | 20:50:08, exit 65 | access violation, read [0x8], at eboot.bin+0x3a0624f; the same moment of the game |
| test, ~20:54 | d02f4696 | (its play log overwritten by the next start) | a recovered GPU hang at 20:56:06–08: GFX page faults (UTCL2), `gfx_0.0.0` and `comp_1.1.0` timeouts, both resets succeeded, devcoredump `20261025-205608-devcd4.txt` |
| test, 20:56:32 | d02f4696 | 21:00:34, exit 65 | access violation, read [0xc], at eboot.bin+0x3d7eca0, the site of exp 0299's L1 crash |

- **Tries 1 and 2 are one path.** Both stack traces run through 0x3af96ce → 0x3af9f84 → 0x3d75a31 (try 2 one level
  deeper, through 0x3ba7610, just after try 1's site). It is the release of a reference-counted object whose first
  field, which should be a vtable, holds a code address. No kernel line and no GPU timeout in either.
- **The pre-0323 build fails too, differently.** So the integration is not the cause of the crashes. The integration
  stays.
- **The F383 crash diagnostics worked:** module + offset of the faulting rip, registers, guest stack trace.
- **The "recent stubbed import" list is not a list of recent calls.** It is the last 12 entries of `g_stubbed_imports`,
  the stubs created at link time, so it is the same in every run. Its NIDs were resolved offline: by grepping the
  public emulators under `refs/` and by hashing 768,721 identifiers from their sources with the NID function (checked
  on known pairs: `memcpy` → Q3VBxCXhUHs, `scePthreadRwlockTryrdlock` → XD3mDeybCnk):
  - LibcInternal: `sceLibcInternalForceTlsDestructor` (tB59hFLH3SA), `sceLibcInternalFinalizeTls` (OQ-dzhlnM28);
  - libkernel:
    - `getrusage` (hHlZQUnlxSM), `sceKernelUtimes` (0Cq8ipKr9n0), `sceKernelTruncate` (WlyEA-sLDf0);
    - `sceKernelChmod` (fgIsQ10xYVA), `sceKernelFchmod` (UtszJWHrDcA);
    - `scePthreadRwlockTryrdlock` (XD3mDeybCnk), `scePthreadRwlockTimedwrlock` (adh--6nIqTk),
      `scePthreadRwlockTimedrdlock` (iPtZRWICjrM);
    - **`sceKernelSyncOnAddressWait8` (dFym5b41JLU), `sceKernelSyncOnAddressWait16` (XgVs4jRehcY)**.
- KytyPlus f266548 has `SyncOnAddressWait` / `Wait32` / `Wait64` / `Wake`, but not the 8- and 16-bit waits. A stub
  returning 0 lets a waiter run on before the value changes. Of the twelve, these are the likeliest to corrupt shared
  objects, together with the timed rwlocks, whose stubs report a lock that was never taken.

**Verdict.** G5 not passed. The crashes are in the title's own code, on a build with and without the integration. The
lead is the unimplemented synchronisation imports. The maintainer asked for them to be implemented as the console
does ("użyć tak jak powinny być użyte a nie robić własne zaślepki"); that is experiment 0327. The test is the same
moment of the game on 0327's private build.
