# 0319 — an hour with RT off on today's shared setup: is it stable enough for G5?

**Question.** The maintainer wants a stable setup for the G5 test ("chcę mieć stabilne stanowisko do testu G5").
His G5 attempt 2 (exp 0315, 2026-10-25) ended twice:
- a box freeze at ~6 min (RT off, no kernel line, reset within seconds);
- an emulator crash at 22 min ("Access violation: Read [0000000000000060]", exit 65). It was first read as the AJM
  ATRAC9 path; F380 (exp 0318) shows that line was stale.

Does today's shared setup run an hour with RT off on S6N's route, and if not, how often does it crash or hang, and
how?

**Known before this experiment.**
- **Today's setup** (exp 0315):
  - the normal build 226bcb82: PlayGo (F361), MangoHud loaded hidden (F367), the 0298 tree;
  - `play-pkg.sh` bb51caf2: the RT-off list with the three traversal programs (F362), `MALLOC_ARENA_MAX=2` (F353),
    the cleanup fix;
  - RT off: the maintainer's saved `RayTracing.PPSA03671=off`, or `KYTY_BC5_RT=0`.
- **Earlier clean runs on S6N's route:**
  - exp 0281 (F351) ran 63 minutes clean with RT off, on 7947154c plus breadcrumbs, with arm A's ten-program list;
  - exp 0280 arm A ran 573 s clean.
  - Neither had today's build or launcher.
- **The private-directory chain** of exps 0299–0314 (`s6n0314.sh`) runs the route without touching the live saves:
  - a launcher derived from `play-pkg.sh` with its own log, working directory, `_SaveData` and
    `KYTY_BC5_SAVEDATA_DIR`, and an input-configuration override;
  - the title reads its saves relative to the working directory;
  - a run must show the route save read (atime) within 60 s.
- **The live saves' sum** is bb14b6dd35b644ff (the box supervisor, 2026-10-25), equal to exp 0315's copy after try 2.

**Setup** (prepared offline 2026-10-25; not run).
- **`s6n0319.sh [runs] [secs] [first] [expected live-saves sum]`** is `s6n0314.sh` adapted. Defaults are 6 × 600 s and
  bb14b6dd35b644ff.
  - **Binary:** the shared normal build as the launcher runs it. It must be md5 226bcb82 on disk and in the running
    process.
  - **Launcher:** `play-pkg.sh` must be bb51caf2. Exp 0299's four edits are renamed to 0319 and their anchors checked
    (7 changed lines, as in 0314). Nothing else changes.
  - **RT off:** a private input configuration with `RayTracing.PPSA03671=off`, plus `KYTY_BC5_RT=0`. A run needs
    RT-off drop lines in its journal by 180 s.
  - **Setup checks that stop the chain:** the private input configuration, save directory and working directory must
    show in the emulator's environment and cwd, and the route save must be read by 60 s.
  - **Per run it records:**
    - duration and how the run ended;
    - the launcher's exit status ("launcher exit N", from a wrapper around the launch);
    - the crash lines with context, from the run's log;
    - kernel lines and TIMEOUT lines;
    - devcoredump paths;
    - flips/s ("VideoOutSubmitFlip took" lines over their span);
    - the RT-off drop lines;
    - the box's memory at the start and end.
  - **Stop rules** (the box supervisor's):
    - a crash (the emulator ends by itself) is recorded and the chain goes on;
    - a hang the kernel recovers from (ring reset succeeded) is recorded and the chain goes on;
    - the machine-down class (reset failed / MODE1) or a live-save change stops the chain;
    - a box freeze ends it by itself.
  - **On HUP/INT/TERM** it stops only its own emulator.
- **`stream0319.sh`** (on the laptop) is exp 0314's `stream0314.sh`: the kernel log and the key journal lines, while
  the chain's lock line is there.
- **`sample0319.sh`** (on the laptop) is exp 0315's `sample0315.sh`. Once a minute while the chain's lock line is
  there, it samples MemAvailable, swap used, GTT used, the emulator's and bc5-mount's RSS, the mount's arena setting
  and the load.

**Plan.** The box supervisor's slot is next; the BVH session's 0316 (RT on) comes after. The runs need the
maintainer's approval in the tcp session, and him reachable for a power-cycle: a freeze like 0315's try 1 leaves the
box down.
1. `stream0319.sh` and `sample0319.sh` on the laptop.
2. `s6n0319.sh 6 600` on the box.
3. Report each run as it lands: duration, flips/s, crash (exit status, exception lines), hang or kernel line. Then
   the memory trend.

**Result.**
- **The chain.** `s6n0319.sh 6 600`, 2026-10-25 16:49:21–17:50:44, ran on the box supervisor's GO, approved by the
  maintainer in the tcp session, with him reachable.
  - Before it, the box was free. The live saves were bb14b6dd35b644ff, the shared build 226bcb82, and `play-pkg.sh`
    bb51caf2 with all four anchors once.
  - The script on the box was md5 e6878cf9. The derived launcher was b737bdc3 (`raw/runs/play-pkg-0319.diff`, 7
    changed lines).
  - The private working directory had 0299's layout (5,151 entries).
  - Console output: `raw/chain.out`. Per-run files: `raw/runs/`, without the play logs. Laptop records:
    `raw/kernel-stream.txt`, `raw/journal-stream-filtered.txt` and `raw/samples.txt`.

  | run | time | end | launcher exit | crash / kernel / TIMEOUT / devcoredump | RT-off drop lines | flips/s |
  |---|---|---|---|---|---|---|
  | S1 | 16:49:21–16:59:34 | 600 s | 0 | 0 / 0 / 0 / 0 | 6,546 | 41.9 (25,017 / 596.8 s) |
  | S2 | 16:59:34–17:09:49 | 600 s | 0 | 0 / 0 / 0 / 0 | 6,517 | 41.4 (24,755 / 597.5 s) |
  | S3 | 17:09:49–17:20:03 | 600 s | 0 | 0 / 0 / 0 / 0 | 6,531 | 41.7 (24,871 / 596.4 s) |
  | S4 | 17:20:03–17:30:17 | 600 s | 0 | 0 / 0 / 0 / 0 | 6,410 | 40.9 (24,367 / 596.0 s) |
  | S5 | 17:30:17–17:40:30 | 600 s | 0 | 0 / 0 / 0 / 0 | 6,557 | 42.0 (25,026 / 595.8 s) |
  | S6 | 17:40:30–17:50:44 | 600 s | 0 | 0 / 0 / 0 / 0 | 6,406 | 40.9 (24,391 / 595.7 s) |

  Flips/s are the journal's "VideoOutSubmitFlip took" lines over their span, start included. The script's own
  flips/s field is empty: its awk put a `>` inside `printf`'s arguments, and the box's awk rejected the line with a
  syntax error (`raw/chain.out`). The counts and spans it printed are right, and the rate is computed from them here.
  "launcher exit 0" follows the script's stop of the emulator at 600 s.
- **Every run passed.**
  - The kernel stream has no amdgpu line.
  - The journal stream has no TIMEOUT or fault line. Its 38,967 "ray tracing off" drop lines are left out of the
    committed copy.
  - In each run the route save was read within 60 s and RT-off drop lines came by 180 s (`<tag>-saves.txt`).
- **The live saves** were bb14b6dd35b644ff after every run and at the end; they were never written
  (`raw/runs/s6n-saves.txt`). The lock was released at 17:50:44.
- **Memory** (`raw/samples.txt`, 61 samples, once a minute). The trend is flat:

  | measure | value |
  |---|---|
  | MemAvailable | ~650 MiB from about 2 min into each run to its end; per-run minimum 590–791 MiB |
  | swap used | 541–786 MiB, ~545–550 MiB from S3 on |
  | GTT | peaks at ~12.1 GB in every run |
  | emulator RSS | peaks at ~6.2–6.5 GB (S2 sampled 3.8 GB at most) |
  | bc5-mount RSS | 711–753 MiB, with `MALLOC_ARENA_MAX=2` in effect throughout |

  There is no growth from run to run, and none within a run after its first two minutes.

**Verdict.**
- **Today's shared setup ran an hour clean with RT off on S6N's route**: six 10-minute runs, with no crash, hang,
  kernel line or GPU timeout, at 40.9–42.0 flips/s and with flat memory.
- **This is not G5.** The maintainer's two failures today came in hand play from his own saves, not on this scripted
  route:
  - the 6-min box freeze with no kernel line (exp 0315 try 1);
  - the host crash at 22 min, "Access violation: Read [0x60]" at guest 0x9047bdfa3. F380 (exp 0318) found it is not
    the AJM decoder; that line was stale, and the real diagnostics were silenced by `--printf-direction Silent`.

  The route plays a fixed stretch and may not reach the code or the state behind either failure. So the soak
  separates the setup's base stability, which held for an hour, from what his session does differently.
- **Next.**
  - A hand session on this setup with the kernel stream and the sampler, waiting a minute before any reset (exp
    0315's note).
  - Exp 0318's crash-log patch, integrated first, so the next crash names its faulting code.
  - Whether a longer or more varied route reproduces the freeze or the crash is open.
