# 0034 — starting a game from a PS5 package

**Question.** With `bc5-mount` reading packages (experiment 0031, F82) and the whole package
on the box, does a game start from the package mount, and if not, what stops it?

**Setup.** The maintainer's own package of a second title (101,814,213,551 bytes, debug,
plaintext outer image; never committed, title not named here), copied to
`~/bc5-data/pkg/game.pkg` and compared by size with the original. `bc5-mount` at commit
2f79517 built in the `ubuntu` container. The host as for ASTRO BOT (patch 0001 at 4b3b656,
`bc5-run.env`), with the system module pack copied once from the ASTRO BOT dump's `fakelib`
into `~/bc5-data/sysmodules-pack` (the package has none). Launcher: `run-pkg.sh` in this
directory (mounts the package, runs the emulator unattended with screenshots and a capture
directory, autopress cross at 40–150 s). One run of 240 s, 2026-10-09 06:42.

**Result.**

| Step | Outcome |
|---|---|
| `bc5-mount inspect` on the whole package | 0.09 s: outer image at 0x10000, 750,239 blocks (616,999 Kraken), inner PFS with 303 inodes, 288 files in 10 directories, 196,628,482,707 bytes |
| `ls -r` | 298 entries |
| `cat eboot.bin` | starts with the SELF magic `54 14 F5 EE` (a fake-signed SELF, as packages built from dumps carry) |
| FUSE mount | 13 entries at the root, mounted in under a second |
| the emulator | loads the executable and its modules from the mount, opens `/dev/gc` and `/dev/dipsw`, sets up AMPR events (`AMPR event add`, three ids) and three `Amm Ring` objects, runs for 20 s (33,881 lines of guest output) |
| the stop | `AMM virtual-memory unmap is unsupported: addr=0x0000001112642b68` (`kernel/memory.cpp`, `KernelHandleReservedRangeAccessViolation`): the game touched a range reserved under the name `AMM` that the host never backs; exit 65 |

**Verdict.** Passed for the package path: the whole package reads, mounts and serves a
game's executable and modules, and the game runs its start-up from it. Failed for the game:
this title maps memory through AMM (the PS5's address map manager, driven by AMPR command
rings), which the host reserves but does not implement, and the first access to an AMM range
ends the run. ASTRO BOT never uses it. Implementing AMM/AMPR mapping is a host kernel task of
its own (KytyPS5 has work on AMPR, noted as a port candidate in F76); it is the next step for
this title, not a package problem.
