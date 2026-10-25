# 0315 — G5 attempt 2: the second title for 60 minutes on the shared build, RT off

**Question.** Does the second title pass gate G5 (`docs/PHASES.md`): a 60-minute hand session on the default shared
build with no GPU hang, fault or machine-down, recorded with the kernel stream? This is the second attempt of the day
(the first was exp 0296).

**Setup.**
- **The session.** The maintainer plays by hand from his own saves, on the desktop shortcut "BC5 emulator" (normal
  build 226bcb82) with `play-pkg.sh` bb51caf2:
  - the PlayGo fix (F361), MangoHud loaded hidden (F367);
  - the RT-off list with the three traversal programs (F362), `MALLOC_ARENA_MAX=2` (F353);
  - the launchers' cleanup fix (2026-10-25 15:47).
- **RT** is off in his saved menu setting (`RayTracing.PPSA03671=off`). The box had been power-cycled at 11:40 and
  ran exps 0300–0314 before. Saves at the start: 8289704a9338a118 (`raw/pre.txt`).
- **Recording** is exp 0296's scripts renumbered (`stream0315.sh`, `sample0315.sh`): the kernel log, the journal
  extract, and a memory sample once a minute.

**Result.**
- **Try 1** (the game from 16:00:44): the box froze at ~16:06, about 6 minutes in.
  - Kernel stream (`raw/try1-kernel-stream.txt`): no amdgpu line; its last line is 16:05:45 (an IPv6 notice). The
    journal extract shows only hold summaries. The memory sample at 16:05:30 was normal: MemAvailable 798 MiB, GTT
    12.1 GB.
  - The maintainer reset the box within seconds ("Komputer się zawiesił. Trwa resetowanie"), at ~16:06:30. Boots:
    the crashed boot's journal ends at 16:05:45, then a 40-s boot at 16:06:37 and the boot at 16:07:34. No
    devcoredump was written.
  - With the reset that fast, a GPU timeout and its ring reset (amdgpu's job timeout) may simply not have come yet.
    Not known: whether it was a GPU hang. The class differs from the day's RT-on hangs, which always logged.
  - Autologin into Plasma worked at that boot (the installer of 12:50). The last autosave, 16:05:10, was complete;
    a copy is in `~/bc5-work/exp0315/saves-after-freeze-160831`, sum 25d6a0f9f4dd78ca.
- **Try 2** (16:10:58–16:33:22, 22.4 min): the emulator crashed, exit 65.
  - The error: "Access violation: Read [0000000000000060] in runtimeLinker.cpp:1111", exception_address
    0x9047bdfa3, with "AJM codec=1, name=ATRAC9 decoder" in the dump. The log is kept as
    `~/bc5-work/exp0315/play-try2.log`.
  - Kernel stream (`raw/kernel-stream.txt`): no amdgpu line.
  - The autosave of 16:33:15 is copied to `~/bc5-work/exp0315/saves-after-crash-163432`, sum bb14b6dd35b644ff.
    The input record of the session (`route-record-try2.txt` on the box) has 56 "hold l3" and 35 "hold r3", so the
    stick clicks reached the title (F379).

**Verdict.** Not a G5 pass. Neither try reached 60 minutes, and the two ended in two different ways: a box freeze
with RT off and no kernel line, and a host crash in the AJM ATRAC9 path, which exp 0299 L1 also hit in the menu.
G5 is postponed until the setup is stable: the maintainer, "odkładamy g5 … chcę mieć stabilne stanowisko do testu G5".
The AJM crash is exp 0318, and an unattended RT-off soak of today's setup is exp 0319. Note for the next freeze: if
the picture freezes, waiting about a minute before a reset lets the kernel log a GPU timeout and its ring reset,
which were missing here.
