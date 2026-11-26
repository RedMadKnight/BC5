# 0202 — one watched session with the AMM window as PRT: no GPU fault in 19 minutes, then a fault-less machine-down

**Question.** Experiment 0199 (F257) traced the second title's TCP write faults to its first-use
clears over AMM pages it never backs. Does `BC5_DIRECT_AMM_PRT=1` (reads 0 and writes dropped there,
experiment 0102) keep a normal play session free of them?

**Setup.**
- 2026-10-22, the maintainer at the box and playing.
- Launch: `~/bc5-work/exp0199/play-prt-0199.sh` (copy here), started over SSH with `setsid nohup`
  at 14:30:19. It is the normal "BC5 emulator" shortcut (`play-any.sh`, the shared build
  `~/bc5-work/kytyplus-build`, the launcher's settings) plus `BC5_DIRECT_AMM_PRT=1`.
- Checked in the game process (pid 394632): `BC5_DIRECT_AMM_PRT=1` in its environment, and
  "bc5-direct: PRT window 0x8000000000+0x1000000000: 0" in the emulator log.
- Learned-fault file unchanged (`~/bc5-work/direct-learned-pkg.txt`, the nine AMM windows included).
  Live saves.
- Journal: `~/bc5-data/captures/play-20261022-1430/gc/direct.log`.
- Box: kernel 7.2.9-ogc3.1. `~/bc5-work/BOX-LOCK` was held from 14:30 to 14:53, and `sync` was run
  before the start.
- The kernel log was streamed to the laptop for the whole session
  (`ssh bc250 journalctl -k -f -n 0 -o short-precise`), so a machine-down could not take it along.
- Meanwhile, by other sessions:
  - experiment 0200 read the game process's memory passively (`/proc/<pid>/mem`, no attach,
    14:33–14:40);
  - the water session took screenshots at the night lake (14:34–14:39).

**Result.**
- 1,155 s of play (45,318 frame-profile lines) with **no GPU fault of any kind**:
  - no kernel page fault line in the stream;
  - in the journal: 0 "timeout: fault", 0 "learned: fault", 0 alias faults and 0 reopens
    (`raw/journal-whole-run.txt`).
  - The learned AMM windows were applied as usual (their holes filled with the zero buffer, 813
    "scratch" lines).
- Four frames took over 1 s (t 260, 667, 687 and 725 s: 1.5, 2.7, 1.2 and 1.4 s), with no timeout.
- At t 1153.46 s a 6,732-dword graphics buffer (#1530444) and an 855-dword compute buffer (#1530453)
  timed out together after 2.0 s. The journal ends there; the timeout probe's dump was not written.
- Kernel (`raw/kernel-stream-1430.txt`):
  - 14:50:13.59: "Dumping IP State", then the device coredump;
  - `comp_1.2.0` timeout, reset succeeded;
  - `gfx_0.0.0` timeout, "Ring gfx_0.0.0 reset failed", "GPU reset begin";
  - 14:50:17.90: MODE1 reset, "VRAM is lost due to GPU reset", PSP resuming;
  - then the SSH stream was cut.
  - Nothing amdgpu between 14:30 and 14:50:13. In particular there is no page fault before the hang.
- The box's own journal of that boot ends at 14:50:00. The hang is only in the laptop's stream.
- The box rebooted twice (`raw/reset-reasons-and-journal-tail.txt`):
  - at 14:50:45: "Previous system reset reason [0x40000400]: a parity error occurred";
  - at 14:51:35: [0x40080400] "software wrote 0x6 to reset control register 0xCF9" and the same
    parity error.
  - It answered SSH again at 14:52.
- Not this experiment's question: at the lake the water session still saw the patchwork come and go
  with PRT on (its experiment 0201).

**Verdict.** Inconclusive for the fix, though it points the right way.
- With PRT, one 19-minute session had no TCP write fault, and no page fault at all.
- The faults are occasional (four among today's sessions), so one clean session does not establish
  the fix. The launcher default stays off.
- The session ended in the fault-less machine-down seen at 07:44 (exp 0192, `BC5_DIRECT_FLAT_APERTURE=1`)
  and 13:41 (exp 0198, prefix journaled): two rings time out with no fault line, and the next boot
  reports a parity error.
- Two of those three ran without PRT, so PRT is not what brings it. What it is stays open.
- New in this one: the GFX ring reset fails, and the kernel falls back to a MODE1 reset that the box
  does not survive.

Next:
- PRT in further sessions, the maintainer's call.
- For the machine-downs, every session's kernel log streamed off the box, as here, plus the end of the
  direct journal. The timeout probe's dump is lost when the box goes down, so the probe would have to
  stream as well. Its fields are exactly what is missing for these three.
