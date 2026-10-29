# 0375 — The registers-only stall sampler under load (T1b)

**Date.** 2026-10-29 08:10–08:16. **Box.** The maintainer installed the sampler; the top session ran ASTRO BOT and
the forced samples while the box was otherwise idle, with BOX-LOCK set.

**Question.** Exp 0374 stopped T1: a forced wave scan under ASTRO BOT came 106 ms before a GPU hang (F520), and
register-only sampling under load had never been tried by itself. Does the sampler hold up under a running game
with the wave scan off (F522's mode)? And what do the CP registers look like in healthy frames?

## Setup

- Sampler: `tools/scripts/gpu-stall-sampler/` from main 77f9586 (`VERSION = "0374"`). It was copied to
  `~/bc5-work/gpu-stall-sampler/`, and `--test` gave `selftest: 11/11 passed` on the box. The maintainer then ran
  `sudo bash ~/bc5-work/gpu-stall-sampler/install.sh` (08:10). The service's start line has `version=0374` and
  `wave_scan=off` (`raw/stalls-log-lines.txt`); the unit runs without `--wave-scan`.
- Box: kernel 7.2.9-ogc3.1, shared normal build, `play-astro.sh` (ASTRO BOT on the direct path), launched at 08:11:39
  through `distrobox enter ubuntu` with `WAYLAND_DISPLAY=wayland-0`, and left on its start screen.
- Load: 18 forced samples (`echo once > ~/bc5-data/captures/gpu-stall/force`). The first 3 came 20 s apart from
  08:13:01, then 15 came 6 s apart (08:14:12–08:15:36). Each sample reads the 33 registers once and the CP header
  histories 8 times.
- Watch: `journalctl -k -f` for the whole run (`raw/t1b-kernel.txt`), and `sudo dmesg` for WARNING and bc5-gpu-watch
  lines afterwards.
- ASTRO BOT's saves were archived before the run (`~/bc5-work/exp0375/astro-saves-before-t1b.tgz`, private). The game
  was closed with SIGTERM at 08:16.

## Result

- **No fault.** All 18 samples read 33 registers with 0 errors, in 0.1–0.2 ms each (`raw/samples.txt`).
  - The kernel stream has no amdgpu line: only `evm` and IPv6 MLD notices.
  - The `sudo dmesg` filter found only the boot-time display-IRQ WARNING (`irq_service.c:129`, at 6.85 s) and
    bc5-gpu-watch's start line.
  - The game ran until it was closed. The package mount went away with it.
  - The second title's saves are unchanged (530ac03cb15b0ddf). As in T1, ASTRO BOT rewrote its own
    `memory.dat` at start-up (08:11:42).
- **The F403 class's CP pointers are the ordinary place of a running frame.** 10 of the 18 healthy samples read
  `CP_PFP_INSTR_PNTR` 0xea0–0xea1 with `CP_ME_INSTR_PNTR` 0x77b, which is F490's and F506's pair:

  | samples | GRBM_STATUS | CP_STAT | PFP | ME |
  |---|---|---|---|---|
  | 8 | 0xe5f14028 / 0xe5f15028 | 0x94078600 | 0xea0–0xea1 | 0x77b |
  | 1 | 0xe7f14028 | 0x95078600 | 0xea1 | 0x77b |
  | 1 | 0xe5d04028 | 0x9c079600 | 0xea1 | 0x56a |
  | 2 | 0xe7f141ac / 0xe7f141ad | 0x94839600 | 0x694 | 0xb8b |
  | 6 | others | | 0x607, 0x614, 0xe9f, 0x172e, 0x1a9d, 0x1aa3 | 0x3c0–0xedc |

  In those 10 samples `GRBM_STATUS_SE0`/`SE1` read 0xee600030 or 0xef600030 (once 0xee600032), never the
  class's 0x0a000016 (`raw/se-status.txt`). F490 places that pair inside the host's GFX-form indirect-dispatch
  check, where the CP waits. A healthy frame
  passes through the same wait, and the samples catch it there more than half the time. What separates the class
  from a healthy frame in these registers is `GRBM_STATUS` 0xa0407028 and SE0/SE1 0x0a000016 (F490), not the
  pointers. The healthy samples read 0xe5f14028 and similar. This is one game on its start screen. The second
  title's healthy frames were not sampled. TODO(verify): the same on the second title.
- T1's hang state (F519, PFP 0xe9f/0xea1 with ME 0xb8b) also has its ME pointer in a healthy sample
  (0x694/0xb8b, 2 of 18). That fits F519: it is not the class's state.

## Findings (for HANDOFF)

- **F523 — The registers-only stall sampler (F522's mode) runs safely under load.** It took 18 forced register
  samples in 2.5 minutes of ASTRO BOT, at 0.1–0.2 ms each, with 0 read errors, no amdgpu kernel line and no
  WARNING. It stays installed for the maintainer's play. Experiment 0375. Medium: one game's start screen, 2.5
  minutes.
- **F524 — PFP 0xea0–0xea1 with ME 0x77b, the CP pointers of every F403-class dump (F490, F506), is where a healthy
  frame's CP waits: 10 of 18 samples of a running ASTRO BOT read them.** The pointers mark the host's
  indirect-dispatch check, not a hang. In those healthy samples SE0/SE1 read 0xee600030 or 0xef600030. The class
  is told apart by `GRBM_STATUS` 0xa0407028, SE0/SE1 0x0a000016, and the fence that stops. Experiment 0375 (`raw/samples.txt`). High for ASTRO BOT; the second title is
  TODO(verify).

## Verdict

**T1b passed.** The register path is safe under load, so the T1 stop (F520) is narrowed to the wave scan. The
sampler stays installed in registers-only mode, so the next F403-class hang in the maintainer's play gets its five
register samples before the kernel's timeout. Wave scans stay off and are not to be retried under load. A program
name would need a different, halting-free source (exp 0370's other paths). F524 means a stall record is read
by `GRBM_STATUS`, the SE status and the stopped fence; the CP pointers alone do not identify the class.
