# CLAUDE.md — BC5

Standing instructions for Claude Code working in this repository. Read `README.md` for the project pitch and `docs/HANDOFF.md` for the research state before doing anything.

## What BC5 is

A user-space GPU backend for running PS5 titles on the AMD BC-250 (Cyan Skillfish, `gfx1013`) on Linux, feeding PS5 AGC/PM4 command streams and native RDNA shader binaries to `amdgpu` without translation. Host runtime: KytyPlus with BC5's patch, every system library written in the host (ADR 0012, D18); RPCSX is a reference for the GPU side only. Plus the tooling around it, starting with `bc5-mount` (FUSE mount for `.ffpfsc` dumps).

Non-goals: booting PS5 firmware, writing a new emulator, anything that touches Sony keys or firmware.

Target hardware: optimisations are made for the BC-250 alone, to use its architecture as fully as
possible. That covers the `gfx1013` GPU (40 CU after the unlock), the 8-core Zen 2 CPU (16
threads), the unified 16 GB GDDR6, the NVMe at PCIe 2.0 ×2, and the `amdgpu` / RADV stack as
installed on the maintainer's box. Portability to other GPUs, CPUs or distributions is not a goal
and does not justify giving up speed on this machine. Examples are build flags such as
`target-cpu=znver2`, the CU and wave layout of this chip, and its memory and storage limits.
Correctness, the hard rules and the experiment discipline still apply.

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
backend/             C++20, the direct amdgpu path (linked into the KytyPlus host as libbc5_backend.a);
                     kytyplus-patches/ the patch against KytyPlus
experiments/
  NNNN-short-name/   one directory per experiment: README.md (question, setup,
                     result, verdict), scripts, raw logs; never edited after
                     the verdict is written, add a new experiment instead
```

## Languages and tooling

- Tools (`tools/`): **Rust 2021**, stable toolchain. FUSE via the `fuser` crate. Error handling with `anyhow`/`thiserror`. Tests with `cargo test`; property tests with `proptest` where parsing is involved. `cargo clippy -- -D warnings` and `cargo fmt --check` must pass.
- Backend (`backend/`): **C++20**, CMake ≥ 3.25, GCC 13+/Clang 17+. `libdrm_amdgpu` for submission. Warnings as errors. Unit tests with Catch2. The backend must build standalone (with a stub host); the host links it as `libbc5_backend.a`.
- Formatting: `rustfmt` defaults; `.clang-format` in `backend/` (LLVM base, 4-space indent, 100 columns).
- License: GPL-2.0 for everything we write (matches KytyPlus and RPCSX). Files copied or ported from elsewhere keep their license and say so in the header. Do not port code from non-open-source or unlicensed repos.
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

- AMD BC-250 on Bazzite (immutable host); builds happen inside the `distrobox` container named `ubuntu` (Ubuntu 26.04; `tools/scripts/bc5-build.sh`); an older `fedora` container exists and is not used for the host (experiment 0006). Assume no root on the host; `sudo` inside the container is fine.
- CPU unlocked to 8C/16T. GPU unlocked to 40 CU by the maintainer's `bc250-cu-live-manager.service`, which rewrites `SPI_PG_ENABLE_STATIC_WGP_MASK` via umr after boot; the kernel and RADV therefore still report 24 CUs (experiments 0003/0004, HANDOFF Q8) — never infer the CU count from them. Do not run that tool or `stock-dispatch` without the maintainer. Recorded versions: kernel 7.2.9-ogc3.1 (`uname -r` on 2026-10-24; F13 recorded 7.2.4-ogc3.1), Mesa 26.2.3 and libdrm 2.4.134 (F13, not re-checked since); re-record them in any GPU experiment whose results depend on them.
- Private data on the box lives in `~/bc5-data/` (mode 700, never inside a git checkout): `ps5-fw/<version>/` the maintainer's own decrypted system software root (private reference data that nothing loads, D18), `games/` own `.ffpfsc` dumps, `mnt/` bc5-mount mountpoints, `captures/` AGC dumps. Nothing from there is ever committed; experiments reference it by path only.
- RPCSX checkout (a GPU-side reference only since D18): `~/src/rpcsx` (commit `e8ae148`), built unmodified in the `ubuntu` distrobox (Ubuntu 26.04, default-PIE GCC) into `~/src/rpcsx/build-ubuntu`; run it from that container. The `fedora` container cannot link it (experiment 0006). Script: `~/bc5-work/build-rpcsx-ubuntu.sh`.
- KytyPlus (GPL-2.0) checkout: `~/src/KytyPlus` (commit `f266548`), built in the `ubuntu` distrobox into the two shared builds, `~/bc5-work/kytyplus-build` (normal) and `~/bc5-work/kytyplus-build-lean` (`KYTY_BC5_LEAN`, every trace compiled out), `kyty_emulator` only, no Qt, with patch 0001 (`backend/kytyplus-patches/0001-bc5-lle-agc.patch`; the copy on main always matches what the shared builds were built from, D19) and the backend archive `~/bc5-work/backend-ubuntu/libbc5_backend.a` (Q19). Launchers: `~/bc5-work/play-pkg.sh` (the second title), `play-astro.sh` (ASTRO BOT), `play-any.sh` (the desktop shortcut); they need the KDE Wayland session (`WAYLAND_DISPLAY=wayland-0`). The box's queue and lock: `~/bc5-work/BOX-QUEUE`, `~/bc5-work/BOX-LOCK` (`PROMPT.md` §1). Shallow clones of IGT (`~/src/igt-gpu-tools`) and Mesa (`~/src/mesa`, sparse) are there for citations.
- Memory split (D8): 512 MiB VRAM carve-out, ~14 GiB for Linux; GTT 13 GiB through `ttm.pages_limit=3407872` (D12). Experiment 0003 was recorded with an 8 GiB carve-out; always re-read `mem_info_vram_total` in memory-sensitive experiments.
- Remote access: the maintainer's laptop reaches the box over SSH (`bc250` alias, key-based). Root is limited to the read-only commands in `/etc/sudoers.d/bc5-claude` (dmesg, drop_caches, `bc250-cu-live-manager status`, `amdgpu_firmware_info`). Idle suspend is prevented by the user unit `bc5-keep-awake.service` (a permanent `kde-inhibit --power --screenSaver`) plus `~/.config/powerdevilrc` `AutoSuspendAction=0`; PowerDevil only reads that file after `systemctl --user restart plasma-powerdevil`. Check with `busctl --user call org.freedesktop.PowerManagement /org/freedesktop/PowerManagement/Inhibit org.freedesktop.PowerManagement.Inhibit HasInhibit` (expect `true`). The BC-250 does not resume reliably from s2idle; Wake-on-LAN is disabled on `enp4s0` (MAC a8:a1:59:b5:ed:fe). Work directories go under `~/bc5-work` on the NVMe, not `/tmp` (tmpfs, fills up).
- Known BC-250 hazards: RADV disables the gfx1013 compute queue, but the kernel's compute rings run dispatches correctly and the direct path uses compute ring 0 for the second title (F177, F178, ADR 0009); a GPU reset can take the whole machine down — save work before running anything with `--submit`.
- GPU coredumps: amdgpu's devcoredump (`/sys/class/devcoredump/devcdN/data`) is root-only and the kernel drops it after 5 minutes. Since 2026-10-24 the maintainer's udev rule `/etc/udev/rules.d/90-bc5-devcoredump.rules` starts `bc5-devcoredump@devcdN.service` (`/usr/local/bin/bc5-save-devcoredump`), which copies each one to `~/bc5-data/captures/devcoredump/<date>-devcdN.txt` (mode 600, the maintainer's user; a `bc5-devcoredump` line in the journal) and fsyncs it, since a dump made just before a machine-down was otherwise lost with the page cache (F332). Installer and undo: `~/bc5-work/devcoredump-setup/install.sh`. These dumps hold the title's command buffers: never commit them; cite them by path.
- Memory: the second title pins ~11.3 GiB of GTT and leaves ~1 GB free on the 15.2 GB box (exp 0288 studies it). To free memory the maintainer had these desktop autostarts turned off on 2026-10-24: Steam (peaked at 4.3 GB; its `steam.desktop` moved to `~/bc5-work/disabled-autostart-20261024/`), KDE Connect, geoclue's demo agent and xwaylandvideobridge (`Hidden=true` overrides in `~/.config/autostart/`), and the Baloo file indexer (`balooctl6 disable`). Undo: move the Steam file back, delete the three overrides, `balooctl6 enable`.
- Phase 0a (`bc5-mount`) needs no BC-250 at all and can be developed on any Linux machine with FUSE.

## Definition of done for a task

- Code builds, lints and tests pass locally (state the exact commands you ran).
- Docs updated (`docs/`, `README.md` if public-facing).
- If the task was an experiment: `experiments/NNNN-*/README.md` has Question / Setup / Result / Verdict filled in and the raw logs are committed.
- The final message to the human summarises what changed, what was verified, and what is still open — no more than ten lines.
