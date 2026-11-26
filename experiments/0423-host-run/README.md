# 0423 — the second title on the Bazzite host instead of the ubuntu distrobox

## Question

Does the second title run the same or better when the emulator runs directly on the Bazzite host, not inside the
`ubuntu` distrobox? The maintainer, 2026-11-15, to the top session's plan: yes, now.

The top session's checks before this experiment:
- the host has glibc 2.44 and the binary needs 2.43;
- every `ldd` library and every library opened at runtime is on the host;
- the Wayland socket is `wayland-1`.

## Setup

- **The binary:** the shared normal `9da2a9d5` (patch `4945ef1b`). The lean binary writes no log, so it has no flip
  counter to compare.
- **`run0423p.sh`**, made by `mk0423.py` from exp0413's `run0413p.sh` (md5 `fc4fe47c`, kept here as
  `run0413p.orig.sh`, not edited on the box). Three edits:
  1. `P_HOST=1` runs the same `/usr/bin/bash -c 'ulimit -l unlimited; exec /usr/bin/env "$@"'` with the same
     environment words and the same derived launcher on the host, without `distrobox enter ubuntu --`.
  2. At 30 s the process's own `/proc/<pid>/maps` is read for the Vulkan driver and MangoHud.
  3. The start file names the place.

  Everything else is `run0413p.sh`'s own:
  - the private working directory, reset from exp 0412's named snapshot (R45; live saves not read);
  - the route gated on the journal;
  - exp 0379's walk to G+240;
  - RT on, `ulimit -c 0`;
  - the kernel-line stop.
- **`chain0423.sh`**: one BOX-LOCK line. Four runs interleaved container / host / container / host (q423c1, q423h1,
  q423c2, q423h2). The chain stops at the first kernel line or real pad key (R55, R51). The laptop streamed the kernel
  log (`raw/kern-0423.txt`).
- **Versions:**

  | | Mesa | Loaded from |
  |---|---|---|
  | host | `mesa-vulkan-drivers-26.2.6-2.fc45` | `/usr/lib64/libvulkan_radeon.so`, `/usr/lib64/mangohud/libMangoHud.so` |
  | container | `26.0.8-1ubuntu0.3` | `/usr/lib/x86_64-linux-gnu/libvulkan_radeon.so`, `.../mangohud/libMangoHud.so` |

  The "loaded from" paths are what each process mapped, read from its own maps. The MangoHud version was not read.

## Result

2026-11-15 18:18:18–18:43:39. Raw output: `raw/chain0423.out`.

| Run | Place | Flips/s (over ~353 s) | Seconds with a gap > 100 ms | Longest gap | G | Kernel / crash lines |
|---|---|---|---|---|---|---|
| q423c1 | container | 25.8 | 59 | 1012 ms | 117 s | 0 / 0 |
| q423h1 | host | 26.7 | 51 | 708 ms | 115 s | 0 / 0 |
| q423c2 | container | 26.0 | 67 | 1003 ms | 116 s | 0 / 0 |
| q423h2 | host | 26.4 | 50 | 2204 ms | 116 s | 0 / 0 |

- All four runs ended clean at G+240 on the same route: the start screen at 87–88 s, the load at 102–103 s.
- No real pad key in any run. The laptop's kernel stream is empty.

## Verdict

**The emulator runs on the Bazzite host. Four of four walks were clean, two of them on the host.**

The host's runs were a little faster:
- 26.7 and 26.4 flips/s against 25.8 and 26.0;
- 51 and 50 seconds with a gap over 100 ms, against 59 and 67.

The longest single gap went the other way in one run (h2: 2204 ms).

Two runs against two is a hint, not a proof (R13). The difference is under 1 flip/s, and no spread between runs was
measured. The two places also differ in more than the container: Mesa 26.2.6 against 26.0.8, and their own MangoHud
builds. So a difference, if real, cannot be laid on the container alone.

Not done:
- a lean run on the host;
- the desktop shortcut on the host (no shared file or shortcut was changed);
- more runs to measure the spread.
