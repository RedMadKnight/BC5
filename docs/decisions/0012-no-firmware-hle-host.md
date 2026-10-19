# ADR 0012 — No PS5 firmware dump, ever: every system library is written in the host

**Status:** accepted (2026-10-19), the maintainer's decision after the work of experiments
0154–0164. Recorded in `docs/HANDOFF.md` §7 as D18; it retires the "track A" half of D11 and
phases 0b and 4 of `docs/PHASES.md`.

## Context

- ADR 0001 and D11 kept two host tracks open: track A, RPCSX booting the console's system
  modules from the maintainer's own firmware dump (the RPCS3 model), and track B, KytyPlus with
  its own stand-ins for the system libraries (HLE). Phase 0b (RPCSX VSH boot) and phase 4
  (the backend inside RPCSX) belong to track A.
- Track A never started: the system software could not be dumped, and every result of the
  project — both titles, the direct GPU path, the tools — was made on track B (F19–F217).
- Track B has now carried the second title from its package through its menus, its saves and
  its opening into gameplay, and ASTRO BOT to "fully playable" (F85, F207, F212), with every
  system library it needed written here or in KytyPlus from public symbol names and the
  titles' own calls (F43, F59, F78, F87–F89, F189, F199, F205, F214–F217) and nothing from a
  console's system software.
- What a loaded Sony module would have given — the console's exact behaviour — the project
  gets by measuring the titles instead, and the hard rules (`CLAUDE.md`) keep Sony material
  out of the repository in any case. A firmware dump would add a private dependency that no
  user of the project can reproduce.
- One exception remains in the tree today: the console-format command stream is built by the
  game's own copies of `libSceAgc` and `libSceAgcDriver`, LLE-loaded from a game dump's
  `fakelib/` directory (F17–F19, D11). They come from a game dump, not from firmware, and are
  handed to the host through `SHADPS4_SYSMODULES_PACK_DIR` (the "system-module pack"): for
  ASTRO BOT its own `fakelib/`, for the second title (a package, which ships none) a copy of
  ASTRO BOT's `fakelib/` without `libSceAmpr.sprx` (experiment 0035). The pack therefore
  supplies today: `libSceAgc.sprx`, `libSceAgcDriver.sprx`, `libScePlayGo.sprx`,
  `libScePsml.sprx` (the last two loaded since experiment 0010, their use untraced).

## Decision

1. **The host does not use a PS5 firmware or system-software dump, and never will.** Unlike
   RPCSX, which boots the console's system modules, every system library a title links against
   is written independently in the host, following KytyPlus's model: from public symbol names,
   public emulators' documentation of the behaviour, and what the titles themselves do
   (experiments). RPCSX stays a reference for the AGC/GPU side only (`/dev/gc` ioctl layouts,
   the PM4 synchronisation packets; F12, `docs/HANDOFF.md` §6). Track A, phase 0b and phase 4
   are closed.
2. **The maintainer's own decrypted system-software root (`~/bc5-data/ps5-fw`) stays private
   reference data.** Nothing is loaded from it, nothing derived from it is committed, and no
   experiment depends on it; it is consulted, if at all, the way a console is consulted — to
   check a behaviour the host then re-derives from the title's calls and cites as an experiment.
3. **The system-module pack is to be phased out of the launchers** (`bc5-run.env`,
   `play-pkg.sh`, `play-astro.sh`, `play-any.sh`) as the host's own libraries cover what it
   provides, in this order: `libScePlayGo` and `libScePsml` first (journal the two titles'
   imports, cover them, drop the files), then `libSceAgc`/`libSceAgcDriver` with an
   independently written AGC driver in the host that emits the public PM4 set the direct path
   already filters and executes (`docs/formats/agc.md`, F19–F21; AnyPS5's GPL-2.0 AGC library
   and recorder driver as the port source, `docs/ports/anyps5-review.md`). The remaining items
   and their gates are open question Q14 in `docs/HANDOFF.md` §3.
4. **Until then the pack is a copy of a game's own `fakelib/`** — game-dump content, never a
   firmware module — and the README says so.

## Consequences

- The public story is one host, one track: KytyPlus plus BC5's direct GPU path plus
  independently written system libraries. "RPCSX as the host" leaves the README's open
  questions.
- A user needs a BC-250, their own dumps and this repository; no firmware, no keys, no
  system-software dump (hard rules 1–3 unchanged).
- The cost is that the host must implement what the console's modules did: the AGC driver's
  initialisation, which today the LLE modules perform and which programs state the host
  leaves at zero (the geometry-engine base of F208, Q13), becomes the host's to write — a
  reason to do it rather than a reason not to.
- AnyPS5 (GPL-2.0) becomes a first-class port source for library behaviour (F214–F217), with
  the provenance caveat of `docs/ports/anyps5-review.md` §1 (no SDK-sourced entries).
