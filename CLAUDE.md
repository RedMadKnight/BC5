# CLAUDE.md — BC5

Standing instructions for Claude Code working in this repository. Read `README.md` for the project pitch and `docs/HANDOFF.md` for the research state before doing anything.

## What BC5 is

A user-space GPU backend for running PS5 titles on the AMD BC-250 (Cyan Skillfish, `gfx1013`) on Linux, feeding PS5 AGC/PM4 command streams and native RDNA shader binaries to `amdgpu` without translation. Host runtime: RPCSX. Plus the tooling around it, starting with `bc5-mount` (FUSE mount for `.ffpfsc` dumps).

Non-goals: booting PS5 firmware, writing a new emulator, anything that touches Sony keys or firmware.

## Hard rules (never break, never ask to break)

1. **No Sony material in the repo, ever.** No firmware, system modules, keys, SDK headers, `.self`/`.prx` from a console, game dumps, `.ffpfsc` containers of real games, decrypted binaries, or links to any of these. If a task seems to require them, stop and say so. Test data is synthetic (built from files we generate) or from open-source homebrew.
2. **Never download, search for, or link to game dumps, torrents, warez sites or "backports".** The project is explicitly anti-piracy. Reference public research code only (see `docs/HANDOFF.md`, "Related projects").
3. **The leaked PS5 BootROM keys are off-limits.** Do not fetch, reproduce, or reason from them.
4. **Register names, packet layouts and hardware facts must cite a source**: a public repo file (path + commit), a public AMD document (name + section), or an experiment log under `experiments/`. Unsourced hardware claims go in a `TODO(verify):` comment, not in docs as fact.
5. **Raw GPU submission can hang the machine.** Anything under `backend/` that submits to `amdgpu` must be behind an explicit `--submit` flag, default off (validation/log-only mode), and must never run in CI or in tests.

## Repository layout

```
README.md            project pitch, public
CLAUDE.md            this file
PROMPT.md            kickoff and per-phase prompts (for humans driving Claude Code)
docs/
  HANDOFF.md         research state: findings, open questions, sources
  PHASES.md          roadmap with gates; one section per phase
  formats/           reverse-engineered/derived format notes (ffpfsc, pfs, pfsc, agc)
  decisions/         ADRs: NNNN-title.md, one decision each
tools/
  bc5-mount/         Rust, FUSE mount for .ffpfsc → app0 directory (phase 0a)
  bc5-agc/           Rust, AGC/PM4 stream decoder + validator CLI (phase 1)
backend/             C++20, the amdgpu backend for RPCSX (phases 2–4)
experiments/
  NNNN-short-name/   one directory per experiment: README.md (question, setup,
                     result, verdict), scripts, raw logs; never edited after
                     the verdict is written, add a new experiment instead
```

## Languages and tooling

- Tools (`tools/`): **Rust 2021**, stable toolchain. FUSE via the `fuser` crate. Error handling with `anyhow`/`thiserror`. Tests with `cargo test`; property tests with `proptest` where parsing is involved. `cargo clippy -- -D warnings` and `cargo fmt --check` must pass.
- Backend (`backend/`): **C++20**, CMake ≥ 3.25, GCC 13+/Clang 17+. `libdrm_amdgpu` for submission. Warnings as errors. Unit tests with Catch2. The backend must build standalone (with a stub host) before it is wired into RPCSX.
- Formatting: `rustfmt` defaults; `.clang-format` in `backend/` (LLVM base, 4-space indent, 100 columns).
- License: GPL-2.0 for everything we write (matches RPCSX). Files copied or ported from elsewhere keep their license and say so in the header. Do not port code from non-open-source or unlicensed repos.
- No network access is needed to build. Do not add dependencies that phone home.

## How to work

- **One phase at a time, one experiment at a time.** Each phase in `docs/PHASES.md` has a gate. Do not start the next phase before the gate is recorded as passed in an `experiments/` directory.
- **Design before code for anything non-trivial**: write or update the relevant `docs/formats/*.md` or an ADR in `docs/decisions/`, then implement.
- **Tests first for parsers.** Every binary format reader gets: a synthetic fixture generator (we can always build a valid container ourselves), round-trip tests, and fuzz/property tests for the header parsers.
- **Small commits with conventional messages** (`feat(mount): …`, `fix(agc): …`, `docs: …`, `exp: 0003 userptr mapping`). Never commit generated binaries or fixtures larger than 1 MB; generate them in tests.
- **When unsure about a hardware fact, write the experiment, not the assumption.** An experiment directory with a clear question and a runnable script is a valid deliverable on its own.
- **Ask before**: adding a new dependency, changing the repository layout, touching anything that submits to the GPU, or when a task would need material covered by the hard rules.
- Keep `docs/HANDOFF.md` current: when an open question is answered, move it to "Findings" with its source, and update `README.md` if the public story changes.

## Machine context (the maintainer's dev box)

- AMD BC-250 on Bazzite (immutable host); builds happen inside a `distrobox` Fedora container named `fedora`. Assume no root on the host; `sudo` inside the container is fine.
- CPU unlocked to 8C/16T. GPU: the handoff assumed 40 CU, but experiment 0003 (2026-09-29) found **24 of 40 CUs active** (HANDOFF Q8). Recorded versions: kernel 7.2.4-ogc3.1, Mesa 26.2.3, libdrm 2.4.134 (HANDOFF F13); re-record them in any GPU experiment whose results depend on them.
- Remote access: the maintainer's laptop reaches the box over SSH (`bc250` alias, key-based, no root). Work directories go under `~/bc5-work` on the NVMe, not `/tmp` (tmpfs, fills up).
- Known BC-250 hazards: RADV disables the gfx1013 compute queue (use the GFX ring); a GPU reset can take the whole machine down — save work before running anything with `--submit`.
- Phase 0a (`bc5-mount`) needs no BC-250 at all and can be developed on any Linux machine with FUSE.

## Definition of done for a task

- Code builds, lints and tests pass locally (state the exact commands you ran).
- Docs updated (`docs/`, `README.md` if public-facing).
- If the task was an experiment: `experiments/NNNN-*/README.md` has Question / Setup / Result / Verdict filled in and the raw logs are committed.
- The final message to the human summarises what changed, what was verified, and what is still open — no more than ten lines.
