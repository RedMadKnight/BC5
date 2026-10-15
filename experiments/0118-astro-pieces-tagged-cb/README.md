# 0118 — ASTRO BOT's tagged-address CB/DB faults come with the graphics pieces, not with the mount

**Question.**
- Run 443 took the machine down with the games' `bc5-mount` back at its pre-0114 binary. Experiment
  0117 had put such hangs down to a changed PFSC reader.
- What do ASTRO BOT's failing runs have in common?
- Does the failure go away without `BC5_DIRECT_PIECES_FULL` (experiment 0077, ADR 0008 step 4)?
  That knob is in ASTRO BOT's `bc5-run.env` since 2026-10-14 09:19.

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present.
- Run 443 (10:28): ASTRO BOT with its play settings (`bc5-run.env`), 70 s, no input,
  `BC5_DIRECT_DRAW_JOURNAL=45:40`. The games' `bc5-mount` is the pre-0116 binary (md5 equal to
  `bc5-mount.before-0116`).
- Runs 444–447 (11:14–11:21): the same settings with `BC5_DIRECT_PIECES_FULL` unset, 70 s each,
  no input. Script: `series-nopieces.sh 444 447` (stops at the first GPU page fault).
- Kernel journal of every boot since 2026-10-13 (`journalctl _TRANSPORT=kernel`), and the `piece:`
  lines of each ASTRO BOT run on 2026-10-15 with the frame-profile time before them.
- Raw:
  - `raw/kernel-gpu-faults-since-1013.log` (both titles);
  - `raw/piece-splits-per-run.txt`;
  - `raw/series-444-447.txt`.

**Result.**

ASTRO BOT's GPU page faults whose address has 0x80 in bits 47:40, with a valid low part:

| time (capture) | run | fault | outcome |
|---|---|---|---|
| 13.10, ~40 runs | — | none | clean |
| 14.10 09:08, 09:12 | — | none | clean (before pieces went into `bc5-run.env` at 09:19) |
| 15.10 00:52 | — | CB/DB `0x800109bc0000` | recovered |
| 15.10 03:01–03:03 | (one capture) | SQC `0x800000005000`, CB/DB `0x8001097c0000`, `0x800109fc0000` | recovered |
| 15.10 09:22 | — | SQC `0x800000005000`, ring timeout | recovered |
| 15.10 10:01 | 439 (0117: "clean") | CB/DB `0x800109fc0000`, `0x800109c00000` | recovered |
| 15.10 10:03 | 440 | journal lost | machine down |
| 15.10 10:28 | 443 | CB/DB `0x8001097c0000`, `0x800109400000`; gfx ring reset failed | machine down |
| 15.10 01:13, 01:16, 01:35, 08:59, 09:02, 09:24 | — | none | clean |
| 15.10 11:14–11:21 | 444–447, **no pieces** | **none** | clean, 54.7–57.2 fps |

- **With pieces:** 6 of the 12 ASTRO BOT captures of 2026-10-15 have such a fault or a lost
  journal.
- **Without pieces:** 4 of 4 are clean. Pieces off is the configuration of the ~40 clean runs of
  2026-10-13.
- **The faulting writes are CB/DB (colour or depth target) or SQC (instruction fetch).** Every
  address is a plausible guest address with 0x80 above bit 40, the class the second title showed
  in experiments 0055–0058.
  - For CB/DB, bits 47:40 come from `CB_COLORn_BASE_EXT` (Mesa gfx10 register JSON, via
    `tools/bc5-agc/regdb`; also used by the host's draw journal).
  - So at the faulting draw that register holds 0x80.
- **Timing.** The faults come where the piece splits come: the ~24,000–28,000-dword frame buffers at
  the start of the second load phase.
  - Run 443: its `direct.log` ends in a burst of ten splits (t 24.52–24.86 s), each with the rest
    behind a 1261-dword full-state prefix. The kernel's fault came 23.5 s after the capture began.
  - Run 439: splits at t 27.6, 30.8 and 31.3 s; the fault came at ~26.5 s after the capture began.
- **Clean runs also split** (08:59: seven splits, two of them in the second load phase). The
  prefix is wrong only sometimes.
- **The prefix.** `full_state::Tracker::emit_prefix()` writes `CLEAR_STATE` and then every
  register the tracker holds, with `SET_*_REG`.
  - It includes values the tracker took from `LOAD_*_REG` tables on the CPU at split time.
  - It includes values from any earlier buffer since the last `CLEAR_STATE`.
- **No mount change was involved in 443.** Hence 0117's verdict ("three of four runs with a changed
  PFSC reader, against none of six without") is wrong on both counts:
  - run 439 had faults that the timeout count did not show;
  - run 443 failed with the old reader.

**Verdict.**
- ASTRO BOT's hangs and machine-downs of 2026-10-15 follow `BC5_DIRECT_PIECES_FULL`, not the
  PFSC reader.
- With pieces, some full-state prefixes put a colour or depth target, or a program, at an address
  tagged 0x80 in bits 47:40. The write faults, and sometimes the gfx ring cannot be reset.
- Which register the prefix gets wrong, and from where, is open. The next step is to journal, at
  every split:
  - the prefix's `CB_COLORn_BASE_EXT` (0x390–0x397) and other `_EXT`/`_HI` address registers;
  - the shader program `_HI` registers;
  - and to compare them with the unsplit buffer's state at the same draw (0072's check, for the
    real buffers).
- Until then, `BC5_DIRECT_PIECES_FULL` should leave ASTRO BOT's play settings. This needs the
  maintainer's yes, as a play-shortcut change.
  - The cost: the water's cross-queue waits go back to the 8 ms limit (F137: spikes, same mean fps).
- 0117 stands as written (frozen); its conclusion is corrected here. 0114 and 0116's PFSC readers
  were reverted for the wrong reason, and could be retested without pieces.
