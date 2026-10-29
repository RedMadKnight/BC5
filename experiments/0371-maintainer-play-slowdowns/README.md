# 0371 — The maintainer's play of 2026-10-28 23:30: slowdowns, a pad replug, and a GPU hang

**Date.** 2026-10-28 23:32–23:36 (observed), 2026-10-29 night (read and written up). **Box.** Reads only: passive streams
during his play, then targeted reads of the crash's records after the reboot. The top session.

**Question.** That evening the maintainer reported "ogromne spowolnienia i liczne przekłamania grafiki" (huge slowdowns
and many graphics glitches) in the second title (shared normal build 1000ad2a, RT on, `play-pkg.sh` 55531ab6). He
restarted the box and played again from 23:30. What do the box's memory and I/O show while he plays? What happened at
his pad replug (23:32:44)? Of which class is the GPU hang that ended the session at 23:36:11?

## Setup

- `stream0371.sh` (laptop): the kernel log (`journalctl -k -f`, from 3 min before) and the play log's audio, pad,
  crash and fault lines (`play-pkg-last.log`), streamed to `raw/kernel-stream.txt` and `raw/playlog-stream.txt` while
  the "MAINTAINER PLAYING | play 2330" BOX-LOCK line stood.
- `sample0371.sh` (laptop): once a minute, one line in `raw/samples.txt` with
  - MemAvailable, swap used (zram) and GTT used;
  - the emulator's and bc5-mount's RSS;
  - bc5-mount's disk reads in the last minute (`/proc/<pid>/io` read_bytes);
  - PSI memory and I/O (full, avg60), the load, and the GPU edge and CPU Tctl temperatures.
- `hang0371.sh` (box, after the reboot, no emulator): the devcoredump's CP and GRBM registers against F490's class
  signature, and the host's timeout-probe lines in the session's journal. The dump and the journal stay on the box
  (`~/bc5-data/captures/devcoredump/20261028-233612-devcd1.txt`,
  `~/bc5-data/captures/play-20261028-2330/gc/direct.log`); only register values and line counts are quoted here.
- Box: kernel 7.2.9-ogc3.1, 15,192 MiB RAM, GTT 13,312 MiB, zram swap 7.4 GiB (zstd), swappiness 60.

## Result

### Memory and I/O during play (`raw/samples.txt`, 4 samples, 23:32:33–23:35:36)

| time | MemAvailable | swap used | GTT used | emulator RSS | bc5-mount RSS | mount reads /min | PSI mem full | PSI io full | load |
|---|---|---|---|---|---|---|---|---|---|
| 23:32:33 | 714 MiB | 592 MiB | 11,967 MiB | 5,803 MiB | 714 MiB | — | 1.14 % | 20.08 % | 10.4 |
| 23:33:33 | 724 MiB | 703 MiB | 12,038 MiB | 1,770 MiB | 704 MiB | 3,873 MiB | 0.92 % | 13.59 % | 9.9 |
| 23:34:34 | 536 MiB | 827 MiB | 12,272 MiB | 1,961 MiB | 712 MiB | 4,371 MiB | 0.89 % | 8.99 % | 8.9 |
| 23:35:36 | 548 MiB | 929 MiB | 12,402 MiB | 1,665 MiB | 703 MiB | 3,041 MiB | 1.29 % | 24.25 % | 13.4 |

- GTT grew by 435 MiB in 3 minutes (about 145 MiB a minute) and stood above exp 0288's RT-off plateau (F353: 11.4 GB,
  +0.5 GB over 29 minutes). GTT used is the whole device's, the desktop's included.
- The available memory stayed between 536 and 724 MiB and zram swap grew by 337 MiB. The emulator's RSS fell from
  5.8 to 1.7 GiB within a minute; its pinned memory is GTT and not in the RSS.
- bc5-mount read 3.0–4.4 GB a minute from the NVMe, about 50–73 MB/s, while its RSS stayed at ~700 MiB. With
  ~0.6 GB available, the package's pages do not stay in the page cache: the game streams its data, and the same data
  is read and unpacked again. F394 saw the same page-cache thrash with RT off, at ~0.7 GB available.
- PSI I/O "full" was 9–24 %: in those minutes all non-idle tasks were stalled on I/O together for that share of the
  time. PSI memory "full" stayed at about 1 %.
- GPU edge 62–74 °C, CPU Tctl 71–75 °C: no thermal limit.

### The pad replug (23:32:44–23:32:49)

The kernel stream has the USB disconnect at 23:32:44.316 and the DualSense back at 23:32:49.283. Afterwards the
maintainer heard the haptics from the speakers. The cause and the fix are exp 0372 (F500–F504).

### The GPU hang at 23:36:11 (`raw/kernel-stream.txt`, the end)

- At 23:36:11.828 the kernel logged "ring gfx_0.0.0 timeout, signaled seq=357942, emitted seq=357944", for process
  kyty_emulator, thread bc5-ring. Two jobs were outstanding.
- The ring reset began at .842 and failed at .874. `bc5-gpu-watch` armed at .877, then crashed the kernel through
  SysRq at .881 ("a ring reset failed … crashing before the full reset"). The box rebooted, and the stream ended with
  the connection.
- The devcoredump was saved as `20261028-233612-devcd1.txt`, and pstore kept four records.

### The hang's class: F403's (`hang0371.sh`, 2026-10-29 01:34, the box idle)

**Devcoredump `20261028-233612-devcd1.txt` (5.9 MB).** Every register value F490 names matches:

| Register | Value | Meaning |
|---|---|---|
| `CP_PFP_INSTR_PNTR` | 0xea1 | in F490's range |
| `CP_ME_INSTR_PNTR` | 0x77b | in F490's range |
| `GRBM_STATUS` | 0xa0407028 | as F490 |
| `GRBM_STATUS_SE0` / `SE1` | 0x0a000016 | waves alive (SE2/SE3 0x6) |
| `GCVM_L2_PROTECTION_FAULT_STATUS` | 0 | no fault ("Faulty page starting at address 0x0") |
| `CP_IB1_BUFSZ` | 0x2ca8 | 11,432 dwords left in the IB the CP was fetching |

The header dumps hold the host's check sequence around `DISPATCH_INDIRECT`:
- PFP: 0x58 `ACQUIRE_MEM`, 0x46 `EVENT_WRITE`, 0x16 `DISPATCH_INDIRECT`, 0x22 `COND_EXEC`, 0x42 `PFP_SYNC_ME`,
  0x37 `WRITE_DATA`, 0x22 `COND_EXEC`, 0x42 `PFP_SYNC_ME`;
- ME: … 0x37, 0x42, 0x37, then 0x45 `COND_WRITE` twice.

That is F490's state exactly. It is the sixth devcoredump of the class.

**The host's timeout probe (journal lines 781,180–781,940).**
- **Which IB.** dcb #287098 (12,487 dwords) timed out at journal t 330.0 s, 2,062 ms after its sync. Its acb #287099
  (68 dwords) holds no dispatch.
- **Content.** The dcb holds 40 dispatches (5 indirect) and 16 waits. The largest grid is 320×180 (57,600 groups),
  so there is no runaway grid. This is the second event of the class without one, after R4 (F491).
- **The same opening as R4's dcb.** It starts with the indirect dispatches 0x11d02a1600, 0x11d02a1800, 0x11d028ae00
  and 0x11d02a1600 (1295×1×1, arguments at 0x11d05df300) at dwords 1289–1419. Then come 0x11d02a3200 (13×8×1) at 1451
  and 0x11d02a2e00 (2956×1×1, arguments at 0x11d0571b00) at 1520.
  - Those are F491's three candidates for R4. R4's dcb #103567 had them at the same offsets (1289–1470) with the same
    argument addresses; only the grid differed (2869 and 3543 there).
  - Where the CP stood relative to them is not mapped. `CP_IB1_BUFSZ` counts the host's IB, not the title's dcb
    (TODO(verify): the host IB's layout around a dcb's indirect dispatches).
  - This family opens most frames' dcb, so its presence alone names nothing.
- **An unmapped HS address.** At dword 10853 the probe found an HS user-data address of 0, not mapped. It is far past
  the head; noted, not taken as the cause.

## Findings (for HANDOFF)

- **F505 — RT-on play runs the box out of page cache, so the title's data is read again and again.** In the
  maintainer's play of 2026-10-28 23:32–23:36 (shared normal 1000ad2a, RT on, bc5-mount 43277724 with F398's
  `POSIX_FADV_RANDOM`):
  - GTT used grew from 11,967 to 12,402 MiB (+145 MiB a minute), above F353's RT-off plateau;
  - MemAvailable stayed at 536–724 MiB and zram swap grew from 592 to 929 MiB;
  - bc5-mount read 3.0–4.4 GB a minute from the NVMe while its RSS stayed at ~700 MiB;
  - PSI I/O "full" was 9–24 %.

  F394's page-cache thrash is still there with F398's over-read fix in: what is read now is needed, but it does not
  stay cached. The memory left to win is the pinned zero pages: F402 found 0.74 GB unforced on the bench, plus
  1.9 GB of zero inside learned 96-MiB windows. Experiment 0371 (`raw/samples.txt`). Medium: four samples in one
  session, no per-frame series.
- **F506 — The GPU hang that ended that play at 23:36:11 is F403's class, the sixth dump of it (F490's state:
  PFP 0xea1, ME 0x77b, `GRBM_STATUS` 0xa0407028, SE0/SE1 0x0a000016, no fault), and the second without a runaway
  grid.** The timed-out dcb #287098 opens with the same indirect dispatches as R4's: 0x11d02a1600, 0x11d02a1800,
  0x11d028ae00 at dwords 1289–1419, arguments at 0x11d05df300. Where the CP stood is not mapped. The ring reset failed
  and `bc5-gpu-watch` rebooted the box. Experiment 0371 (`hang0371.sh`; devcoredump and journal private on the box).
  High for the class; the program is still unnamed (exp 0370's sampler).

## Verdict

- **Slowdowns.** The box's memory shows the conditions for them. The title's data no longer fits in the page cache
  next to the ~12 GiB the title pins with RT on, so bc5-mount re-reads it at 50–73 MB/s and every task stalls on I/O
  9–24 % of the time.
- **Graphics glitches.** The session saw no picture. Late streaming fits this memory state, but it is not shown.
- **The lever left.** The pinned zero memory (F394, F402): narrower learned windows, or lazy unforced ranges in
  RenderGpuWcLarge and CommitIABufferAllocator. Each needs its own experiment.
- **The replug.** Explained and fixed in exp 0372.
- **The crash.** F403's class, still the one RT-on machine-down risk. Exp 0370's resident sampler is what can name the
  program; its first stage is built as exp 0373.
