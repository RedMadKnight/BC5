# 0318 — The second title's crash reading [0x60] at guest 0x9047bdfa3

**Question.** On 2026-10-25 at 16:33:22, after 22.5 minutes of the maintainer's play (normal shared build 226bcb82,
the G5 attempt of experiment 0315), the emulator ended with exit 65: "Access violation: Read
[0000000000000060] in runtimeLinker.cpp:1111", exception_address 0x9047bdfa3. The dump also shows
"AJM codec=1, name=ATRAC9 decoder". What does the title's code at 0x9047bdfa3 read at +0x60, and why is that
pointer null on our host? Is the AJM/ATRAC9 path involved (F300/F301's vgmstream decoder for the haptic
configurations 6/7)?

**Setup.**
- Offline, on the laptop: KytyPlus `f266548` with main's patch 0001 as of `ffd0e49`, applied in the scratchpad as in
  experiment 0317: `src/libs/ajm.cpp`, `src/libs/ajm/atrac9_decoder.h`, `src/common/hostException.cpp`,
  `src/common/assert.cpp`, `src/common/logging/log.cpp`, `src/loader/runtimeLinker.cpp`. Also experiment 0205's
  kept crash dump (`../0205-lake-water-tile-pages/raw/B1-crash.txt`), experiment 0299's L1 note and experiment
  0310's S2/S3 notes.
- Box: `reads0318.sh` lists the read-only greps of the crash log `~/bc5-work/exp0315/play-try2.log`. The top session
  ran them itself on 2026-10-25 at about 17:00, while only a CPU-side bench ran. This session's own attempt stopped at
  its guard, and the copy of the script to the box was refused as a shared write.
- The change: `patch0001-crashlog.diff`, a diff of `src/loader/runtimeLinker.cpp` against KytyPlus `f266548` plus
  patch 0001 as of `ffd0e49` (unchanged on main since). `swap0318.pl` made its mechanical part (`LOGF(` and the one
  `LOGF_COLOR(` in lines 875–1114 → `Bc5CrashLog(`); the helper, the include and the added call were written by hand.
  `git apply --check` passes on that tree (laptop). It was not built here: the laptop has no compiler.

**Result (offline part, 2026-10-25).**
- **"AJM codec=1, name=ATRAC9 decoder" is a stale stdout line, not part of the dump.**
  - `ajm.cpp:384–394` (`AjmLogCodecSupport`) prints it once per process with `std::printf`. That happens when the
    first instance of a supported codec is created, at the title's start.
  - The register dump goes out through `RawLog` (`hostException.cpp:67–121`). Then `EXIT` prints
    "--- Build ---" and the stack trace through stdout (`assert.cpp:27`), which flushes whatever was still
    buffered there. With the session's logging off (`log.cpp:219–247`: `BC5_LOGGING=0` or the menu switch), no
    `LOGF` flushes stdout before then.
  - So the line lands between the registers and "--- Build ---" in every crash of a run whose stdout still held
    it. That is so in experiment 0205's B1, a write fault in host code at 0x7fa85dd7fbb7 16 s into a run. It is so
    in experiment 0299's L1, a read of 0xc at guest 0x903d7eca0. And it is so in this crash.
  - It names the first codec the title opened, not the code that faulted. To be confirmed on the box: it occurs
    once, near the crash block.
- **The AJM HLE gives the title no null pointer to follow.**
  - `AjmBatchStart`/`AjmBatchWait`/`AjmBatchErrorDump` (`ajm.cpp:891–936`) return OK with the `AjmBatchError`
    zeroed. The jobs run when they are queued, and their outcome goes into the title's own sideband buffers
    (result codes, consumed and produced sizes, sample counts).
  - The ATRAC9 decoder, vgmstream's included (`ajm/atrac9_decoder.h`), runs in host code. A fault in it would have
    a host exception address (0x7f…/0x56…), not 0x9047bdfa3 in the title's range.
  - Whether a decode result (for example `AJM_RESULT_CODEC_ERROR | AJM_RESULT_FATAL` from a frame the decoder
    rejects) sends the title down a path that dereferences a null object is not visible offline.
- **What the handler logs, and when.** Before `EXIT`, `runtimeLinker.cpp:875–1112` logs the following through
  `LOGF`, so only with logging on:
  - the exception module (`dladdr`) and 32 code bytes at the fault;
  - the registers, and 16 stack words with their guest code;
  - a guest stack trace with module and offset;
  - eight qwords at each register;
  - the last 12 *stubbed (unresolved) imports* the title called.

  An unresolved import's stub returns 0, so a title that reads [ret+0x60] right after one would crash exactly like
  this. Those lines name the import if logging was on. The `RawLog` register dump is written either way.
- **Other crashes with "runtimeLinker.cpp:1111" are not the same site by the evidence kept:**
  - experiment 0299 L1: read 0xc at 0x903d7eca0;
  - experiment 0310 S2/S3: reads at 0x1d880 and 0x4dfac, after recovered GPU hangs;
  - experiment 0205 B1: a host write.

  Line 1111 is the handler's own `EXIT` for every access violation the host does not resolve. It does not mark a
  location.

**Result (box, read by the top session, 2026-10-25 ~17:00).**
- `play-try2.log`: 18,589 lines, 1.46 MB, header "== 2026-10-25 16:10:58 emulator 2026-10-25 12:49:02".
- No `BC5_LOGGING` line in `bc5-run.env` or `play-pkg.sh`: the session's logging switch was on.
- Still, the log holds none of the handler's `LOGF` lines (no `kyty_exception_handler`, exception module, `code-32`,
  stack trace or `guest r.. =`), and no unresolved-import or late-resolved line in the whole session.
- Its tail is exactly the `RawLog` register dump, "AJM codec=1, name=ATRAC9 decoder" (line 18582, its only
  occurrence), "--- Build ---" and "Access violation: Read [0000000000000060] in runtimeLinker.cpp:1111", exit 65.
- The reason: `play-pkg.sh` (line 187) and `play-any.sh` start the emulator with `--printf-direction Silent`, so every
  `LOGF` goes nowhere, the crash diagnostics included. Only `RawLog`, plain `printf` and `EXIT` reach the play log.
- So the AJM line is the one stale stdout line predicted above, and the crash's site is not in the log.

**The change (`patch0001-crashlog.diff`, for integration with the maintainer's yes, D19).**
- `Bc5CrashLog(format, ...)` in `runtimeLinker.cpp`: `vsnprintf` into a fixed per-thread line buffer, written to
  stderr through `RawLog` at each newline. No allocation, no `fmt`. It is independent of the printf direction
  and of the logging switch, and has a `format(printf)` attribute so the compiler checks every call.
- The handler's terminal block (from `kyty_exception_handler` to its `EXIT`, after every recoverable branch has
  returned) uses it for all 32 former `LOGF`/`LOGF_COLOR` calls. The argument types were checked against their
  formats, because `vsnprintf` does not forgive a mismatch the way `fmt::sprintf` did.
- One added call, `dump_guest_code("exception rip", info->exception_address)`: the faulting instruction's program
  file and offset (`eboot.bin`+…) with 16 bytes either side. So the next crash names its site directly, without
  `/proc/<pid>/maps`.
- Nothing changes until something crashes: the block runs only on the way to the `EXIT`. The cost is a few dozen
  lines in the play log at a crash.
- The launchers' `--printf-direction Silent` stays: a printf file would flood the log.

**Verdict.** Partly settled.
- The AJM/ATRAC9 lead is dropped: the line is a stale stdout line flushed by `EXIT`, present in unrelated crashes.
- The AJM HLE gives the title no null pointer to follow.
- Why the crash log names nothing: the launchers silence the handler's diagnostics. `patch0001-crashlog.diff`
  restores them without touching the launchers.
- Open: what the title reads at [0x60] from 0x9047bdfa3. It needs either the next crash with the change built in,
  or the mapping of 0x9047bdfa3 to `eboot.bin`+offset from a running session's `/proc/<pid>/maps` (as experiment
  0313 did) and a disassembly of those bytes on the box. Neither the code bytes nor a disassembly go into this
  repository.
