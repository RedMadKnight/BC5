# 0114 — one inflate per PFSC block (ASTRO BOT's .ffpfsc): slower loads and GPU timeouts, reverted

**Question.** Experiment 0112 made the package reader decode each block once. Does the same change
help the PFSC reader, which serves ASTRO BOT's `.ffpfsc` dump (zlib, 64 KiB blocks, a 256-block
cache)?

**Setup.**
- Change, tried and reverted:
  - `src/pfsc.rs` takes 64 decode stripes, as the package reader does;
  - a missing block inflates under its stripe's lock after a second cache check;
  - it is counted in `bc5_mount::stats`.
- Unit tests and clippy passed.
- ASTRO BOT with its play settings (`bc5-run.env`), 60 s, no input, `BC5_MOUNT_STATS=1`.
  2026-10-15, maintainer present:

| run | time | `bc5-mount` |
|---|---|---|
| 426 | 08:59 | as committed (39ad030) |
| 427 | 09:02 | with the change |
| 428 | 09:22 | with the change, again |
| 429 | 09:24 | change reverted, rebuilt |

**Result.**

| run | GPU job timeouts | 2nd load phase (bytes served) | outcome |
|---|---|---|---|
| 426 | 0 | 25–31 s, to 4.5 GB | clean |
| 427 | 4 | — | the machine went down at ~09:02:24 |
| 428 | 2 | 40–46 s, to 5.6 GB | ran to the end |
| 429 | 0 | 25–30 s, to 4.5 GB | clean |

- **Run 427.** A CPU-side `WAIT_REG_MEM64` on 0x400202140 timed out after 2 s at 49.5 s. A
  4749-dword graphics buffer then failed with a timeout after 2.9 s, its CS ioctl taking 313 ms.
  The kernel logged nothing more: the ring reset took the machine down (F110 class). The
  maintainer restarted it.
- **Run 428** decoded 7495 MiB for 5582 MiB served, 40,688 blocks again. With 64 KiB blocks and a
  16 MiB cache, evictions dominate.
- Every other ASTRO run of the day had no timeouts: 0052, 0113, 0116, 0135 and 0859.
- The second title's runs with the package-reader change (0112, 0113) had no timeouts either.

**Verdict.** Failed and reverted. With this change, ASTRO's load stretched by 15 s and two of two
runs hit GPU timeouts; one took the machine down. Changing when its data arrives exposes a timing
hazard in ASTRO's cross-queue waits. `src/pfsc.rs` is as in 39ad030, and the mount was rebuilt
from it. The package reader (0112) keeps its change; the second title shows no timeouts with it.
Any further mount changes are checked against ASTRO too, with the maintainer present.
