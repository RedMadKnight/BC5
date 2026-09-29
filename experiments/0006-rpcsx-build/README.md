# 0006 — RPCSX builds on the BC-250

**Question.** Does RPCSX build on the BC-250 dev box from unmodified sources, and what does it take?
(docs/PHASES.md phase 0b, task 2.)

**Setup.** BC-250 dev box, 2026-09-29 (state of experiments 0003–0005, D8 memory split).
RPCSX `e8ae1481ab7ba04d5c6bef89dd852aabba2c88ff` (2026-06-30), `git clone` plus
`git submodule update --init --recursive --depth 1 --jobs 8` (full-history submodules — FFmpeg,
LLVM — were too slow over the link; the build needs no history). Build commands as in RPCSX's
`.github/BUILDING.md` and CI: CMake + Ninja, `Release`, `-march=native`, `-j8` (7.5–14 GiB RAM).
Long jobs ran under `kde-inhibit --power --screenSaver` via `nohup`; scripts in `raw/`.

Two containers were tried:

1. `fedora` distrobox — Fedora 44, GCC 16.2.1 (configured **without** `--enable-default-pie`),
   CMake 4.3.0; dependencies `cmake gcc-c++ libunwind-devel sox-devel ninja-build alsa-lib-devel nasm
   systemd-devel libxcb-devel libX11-devel wayland-devel libxkbcommon-devel libXrandr-devel
   libXinerama-devel libXcursor-devel libXi-devel libXext-devel vulkan-headers vulkan-loader-devel`.
2. `ubuntu` distrobox (created for this) — Ubuntu 26.04.1 LTS, GCC 15.2 (**with**
   `--enable-default-pie`), CMake 4.2.3, Mesa 26.0.8; dependencies = the apt list of RPCSX's CI
   (`.github/workflows/rpcsx.yml`) plus `g++ mesa-vulkan-drivers vulkan-tools libvulkan-dev`.

**Result.** Excerpts of all five build logs: [`raw/build-excerpts.log`](raw/build-excerpts.log).

| Attempt | Container / flags | Outcome |
| --- | --- | --- |
| 1 | fedora, as documented | 553/554 compiled in 347 s; link of `bin/rpcsx` fails: `relocation truncated to fit: R_X86_64_32S` |
| 2 | fedora, `-fPIE` for C/C++ via CMake | same error, now from the bundled FFmpeg (built by its own `./configure`, which does not see CMake flags) |
| 3 | fedora, + `CFLAGS=-fPIE` for FFmpeg (it then enables `pic` itself) | `failed to convert GOTPCREL relocation …; relink with --no-relax` |
| 4 | fedora, + `-Wl,--no-relax` | `relocation truncated to fit` against `__TMC_END__` / `.tm_clone_table` — from GCC's own non-PIC `crtbegin.o` |
| 5 | **ubuntu, unmodified** | **554/554 in 339 s**; `bin/rpcsx` 92 MB, `rpcsx --version` = `v20260630-e8ae148 Draft`; `vulkaninfo` in the container: `AMD BC-250 (RADV GFX1013)`, Mesa 26.0.8 |

Cause of 1–4: RPCSX links `bin/rpcsx` at a fixed high address
(`target_base_address(rpcsx 0x0000070000000000)`, `rpcsx/CMakeLists.txt:84`; the helper in
`CMakeLists.txt:123-131` turns `POSITION_INDEPENDENT_CODE` off and passes `-Ttext-segment`) and
links with `-no-pie` (`cmake/ConfigureCompiler.cmake:101`). That only works when every object —
including the compiler's start files — uses RIP-relative addressing, which a default-PIE toolchain
provides and Fedora's GCC does not.

**Verdict.** Phase 0b task 2 done: RPCSX builds from unmodified sources on the dev box inside an
Ubuntu 26.04 distrobox (`~/src/rpcsx/build-ubuntu`), and the container sees the GPU through RADV.
Fedora needs a default-PIE toolchain (or an RPCSX change) and is not used for RPCSX. Per the
maintainer, nothing is reported upstream. Next: phase 0b task 3 (boot VSH / safe mode) needs the
maintainer's own decrypted PS5 system software in `~/bc5-data/ps5-fw/<version>/`; RPCSX documents
only PS4 5.05, so PS5 mode (`FwType::Ps5`, `--fw`, `--system`) is expected to need investigation.
