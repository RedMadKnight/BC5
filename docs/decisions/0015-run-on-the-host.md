# ADR 0015 — Build in the container, run on the host

**Status:** decided 2026-11-24 (the maintainer: the emulator runs in the normal OS, not inside a
distro container; in the end one shortcut for the normal build and one for lean, both without the
container). The switch-over on the dev box follows the plan below; the host-vs-container lean A/B
and the function runs are its gate, recorded in an experiment directory. Gate passed 2026-11-24
(HANDOFF F920). Amended the same day: the build moves to the host too (last section); until that
is done, "the build stays in the `ubuntu` distrobox" below is what is true.

## Context

- Since phase 1 everything ran inside the `ubuntu` distrobox (Ubuntu 26.04): the build, and also the
  emulator, the launchers and `bc5-mount` (shortcuts `distrobox enter ubuntu -- ~/bc5-work/play-any.sh`).
- A third shortcut, *BC5 emulator (lean, host)* (2026-11-15), already ran the lean build straight on
  the Bazzite host: 4 of 4 walks clean, 26.7/26.4 against 25.8/26.0 flips/s in the container
  (exp 0423, a hint).
- Host runs started over ssh get no rtkit realtime unless started through the user manager
  (`systemd-run --user`; F860, LESSONS R65). Started from the Plasma session they do.
- Read on the box on 2026-11-24 (image 45.20261123, kernel 7.3.4-ogc10.1):
  - the shared normal `fd8e44e1` and lean `1e47486a` need 8 libraries (libm, liblzma, libopus,
    libdrm_amdgpu, libdrm, libstdc++, libgcc_s, libc), all in the host's `/usr/lib64`;
  - their highest symbol versions are GLIBC_2.43 and GLIBCXX_3.4.32; the host has glibc 2.44 and
    GLIBCXX_3.4.36 (the container: glibc 2.43);
  - SDL is linked in and opens its backends at run time: 18 of the 20 names are on the host, the two
    missing ones (libjack, libsndio) are audio backends BC5 does not use (PulseAudio through
    pipewire-pulse);
  - `bc5-mount` `1aa3866a` needs libc and libgcc_s only; the host has `fusermount3`;
  - on the host the emulator gets RADV 26.3.1 and libdrm 2.4.134 instead of the container's 26.0.8
    and 2.4.131;
  - `SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS=0` comes from the user manager's environment
    (`systemctl --user show-environment`), not from the container, so host runs get it too.
- The host has GCC 16.2.1 but no cmake, ninja, clang or Rust, and none of the headers the build needs
  (Vulkan, libdrm's `amdgpu.h`, fuse3, PipeWire, SDL2). A host build would need packages layered
  onto the immutable image, or Homebrew, whose libraries would end up in the binary.

## Decision

- The build stays in the `ubuntu` distrobox (`tools/scripts/bc5-build.sh`, `bc5-install.sh`).
- Everything that runs a game runs on the host: the launchers, the desktop shortcuts, `bc5-mount`,
  and every test harness. Over ssh, a run starts through `systemd-run --user`.
- Every build is checked for the host by `tools/scripts/host-deps-check.sh`, run on the host:
  - every library comes from the host's `/usr/lib64`;
  - no symbol version is newer than the host's glibc and libstdc++;
  - the run-time libraries BC5 uses are known to the host's `ldconfig`.
  `bc5-build.sh` and `bc5-install.sh` run it after each build. Build kits run it before a swap. An
  Ubuntu update that moves the container's glibc past the host's fails there, not at a player's start.
- The desktop ends with two BC5 shortcuts, *BC5 emulator* (normal) and *BC5 emulator (lean)*, both
  `env BC5_LEAN=0|1 ~/bc5-work/play-any.sh` without the container.
- Title launchers carry no behaviour switches. What a title needs is a default of the build for every
  title (ADR-less rule of 2026-11-22, D26). On 2026-11-24 the second title's `play-pkg.sh` lost the
  words that are gone from the build or equal to its defaults. Three words stay until the build has
  their universal form (next section).

## Words kept until the build has them

The second title ran with the launcher stripped of every word on the host, from the NAS package, on
2026-11-24 (tag h442nas1). It ended 3.9 s after the start, before the start screen: a CB/DB write into
the heap "AMM", whose 2 MiB chunk had never been imported (fault record `20261124-141525`, exit 86).
The direct path imports a view's 2 MiB chunks only where the CPU has written data (`lseek(SEEK_DATA)`,
`direct_sync_one` in patch 0001), plus the chunks a submission names:
- PM4 memory operands and user-data V#s (k1f412, ud434);
- a ±32 MiB window around the CB/DB/HTILE bases (`hint_targets`).
A heap that only the GPU writes is therefore missing, unless a launcher lists it as eager. These
three words stay in `play-pkg.sh`, marked for replacement:

| word | why | universal form to build |
|---|---|---|
| `BC5_DIRECT_EAGER_NAMES` += 17 heaps (exp 0042, F88, F96) | the GPU writes them before the CPU does | the build imports every view the title maps with GPU access, at its map, for every title, with no name list. The bake-2 row mw439 (`BC5_DIRECT_EAGER_GPU_WRITE`, the map's GPU-write bit) is this rule for writable views; on the first title it costs +5.6 GiB GTT and long frames, so its cost must be explained and reduced before it replaces the list |
| `BC5_DIRECT_LAZY_NAMES` += 4 CPU-only heaps (exp 0330, F394) | 242 MiB less pinned | follows from the row above: a view mapped without GPU access is never imported unless a submission names it |
| `unset BC5_DIRECT_FLIP_DEFER` (exp 0080/0081, 0171) | deferred flips lose this title's menu glyphs | `bc5-run.env` defers flips for every title. Either the deferral goes from the shared env file (every title flips undeferred, as this one does), or the glyph loss gets its source fixed |

## Consequences

- The emulator's Vulkan driver and libdrm are the host's, and they change with each image update.
  GPU experiments re-record `rpm -q mesa-vulkan-drivers libdrm` as before.
- `pad-volume.sh` no longer needs `distrobox-host-exec`. The patch's diagnostic hang dump
  (`BC5_DIRECT_UMR_ON_TIMEOUT`, off by default) still calls the host through `distrobox-host-exec`.
  On the host that call fails, so it waits for the next bake to call `sudo -n` directly.
- The `fedora` container is unused. Removing it is the maintainer's call. The `ubuntu` container stays
  for the build.
- Undo: put the distrobox shortcuts back from `~/bc5-work/trash-20261124/pulpit/` and the
  `.before-host` copies of the box scripts; the binaries do not change.

## Amendment 2026-11-24: the build moves to the host too

**Status:** decided and approved by the maintainer on 2026-11-24, the downloads approved; **built and
accepted the same day** (HANDOFF F928; the results below). `bc5-build.sh` and `bc5-install.sh` build on
the host (branch `feat/host-toolchain`). The containers stay until the top session's yes to remove them.

- **Decision.** The build leaves the container as well, and the distrobox containers (`ubuntu`,
  `fedora`) are then removed from the dev box.
- **Why the Context's objection no longer holds.** The Context said a host build would need packages
  layered onto the immutable image, or Homebrew, whose libraries would end up in the binary. The form
  chosen needs neither.
- **Form.** A private toolchain under `~/bc5-toolchain` on the box. No `rpm-ostree` layering, no
  linuxbrew library in the link, no sudo:
  - clang 21.1.8 with lld from the LLVM release, the compiler every BC5 build has used (in the
    container it was Ubuntu's clang 21.1.8), so a host-built binary differs from a container-built
    one only by its environment;
  - cmake 4.2.3 and ninja 1.13.2 from their upstream releases;
  - Rust 1.93.1 through rustup, with its homes inside the toolchain directory;
  - a sysroot of 30 `-devel` RPMs at the host's exact installed versions, unpacked and never
    installed. They are used for their headers only: the link is against the host's real libraries
    in `/usr/lib64`.
- **One script** makes it: `tools/scripts/bc5-toolchain.sh` (branch `feat/host-toolchain`; run and
  accepted on the box on 2026-11-24, HANDOFF F928).
- **Acceptance before the containers go.** Host-built normal, lean and `bc5-mount` must pass:
  - `tools/scripts/host-deps-check.sh`;
  - the backend's Catch2 tests and the det tests;
  - The first title function runs on both builds;
  - a lean A/B against the container-built binaries, with a null arm.
- **Consequences.**
  - An image update that changes an installed library version needs the sysroot rebuilt to match.
  - `bc5-build.sh`, `bc5-install.sh` and README's Build section changed with the switch-over
    (feat/host-toolchain): a fresh install makes the toolchain, not a container.
  - The Consequences line above, "the `ubuntu` container stays for the build", ends when the
    acceptance list has passed.

### Acceptance, 2026-11-24 15:50-16:46 (boot of 15:12; HANDOFF F928)

- The toolchain: clang/lld 21.1.8, cmake 4.2.3, ninja 1.13.2, Rust 1.93.1, and a sysroot of 30 RPMs.
  - Every download is checked against its publisher, and the manifest is in `~/bc5-toolchain/dl/MANIFEST`.
  - Five stub `.pc` files cover modules that the sysroot names only as `Requires.private`.
  - PipeWire's `libjack.so` is linked where SDL looks for it.
- Two build differences from the container:
  - `-DSDL_SNDIO=OFF`: Fedora has no sndio.
  - `-include cstdint` for C++. The host's libstdc++ 16 no longer pulls `<cstdint>` in, and KytyPlus's
    `gpu_translator.h` relies on that. The real fix, a one-line include in the patch, is on the next-bake list.
- The builds of the shared tree 8a9ed0cf:

  | | Host-built | Container-built |
  |---|---|---|
  | normal | `63a875a5`, 175.6 MB | `fd8e44e1`, 177.8 MB |
  | lean | `9905a69e`, 173.5 MB | `1e47486a`, 175.7 MB |
  | bc5-mount | `10fcfc89` | `1aa3866a` |

  - All three host-built binaries pass `host-deps-check.sh`.
  - Their warnings are mostly libstdc++ 16 deprecations; see F928.
- The tests: Catch2 345 of 346 (1 skipped), the det tests all PASS, and the plants all FAIL. That is the same
  as the container run on the same inputs.
- The first title on the host: the host-built normal passes, and the lean A/B per R74 gives:
  - host-built: 58.36, 58.74, 58.14 flips/s;
  - container-built: 58.38, 58.44, 58.05;
  - null arm: 58.59, 58.40, 58.80.

  No loss: every host-built run lies inside the container-built spread. GTT and realtime threads are equal.
- Before the `ubuntu` container can go: the shared build directories (`kytyplus-build`, `kytyplus-build-lean`,
  `backend-ubuntu`) are still configured by the container's clang. A bake must rebuild them with the host toolchain
  in fresh directories first; until then an incremental rebuild of the shared builds still needs the container.
  *Done 2026-11-24 17:23 by bake H (HANDOFF F931): the shared build directories are host-configured; the container-built
  ones are kept as `*.container-1124`.*
