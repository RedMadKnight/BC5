# 0002 — bc5-mount gate (G0a)

**Question.** Does mounting a synthetic container yield a file tree and per-file SHA-256 identical to
the source directory, with `cargo test` green and ≥ 300 MB/s sequential read (docs/PHASES.md, gate
G0a)?

**Setup.** Two parts, because the FUSE layer only builds on Linux.

*Part A — reader path, Windows 11 (maintainer's laptop, Ryzen "Family 25 Model 33", NVMe).*
Rust 1.98.1 (`stable-x86_64-pc-windows-gnu`), `tools/` at commit `58cd27c`. Commands:

```sh
cd tools
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
cargo test --release --test roundtrip sparse_1g -- --ignored      # 1 GiB sparse preset
cargo build --release
bc5-mount inspect  "<own dump>.ffpfsc"
bc5-mount verify   "<own dump>.ffpfsc" > verify.txt               # hashes every file
```

The last two use the maintainer's own dump (PPSA21567, 47.5 GB container). Only structure and
throughput are recorded here; no listing or hash of the dump is committed.

*Part B — FUSE mount, Linux.* [`run.sh`](run.sh): builds `bc5-fixture`/`bc5-mount`, builds a preset,
mounts it, compares `find`/`sha256sum` output of the mount with the materialised source tree,
measures `dd bs=1M` throughput on the largest file, and runs MkPFS as an oracle if installed.
To be run on the BC-250 in the `fedora` distrobox (needs `fuse3`, `fuse3-devel`, `pkg-config`).

**Result.**

Part A (Windows):

| Check | Result |
| --- | --- |
| `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` | clean |
| `cargo test` | 31 unit + 10 integration tests pass, 1 ignored (3.7 s) |
| `sparse_1g` (1 GiB logical, 16 384 PFSC blocks, grown offset table) | pass, 55.6 s release (build + verify + materialise + rebuild) |
| Each of the three `feat(mount)` commits checked out alone | `cargo check --all-targets` clean |
| `inspect` on the real container | 2.6 s: 166 723 files, 2 145 directories, 159.8 GB of file data, 2 501 536 PFSC blocks (2 423 800 compressed), exFAT cluster 32 KiB, title read from `param.json` |
| `ls -r` on the real container | 168 868 entries, no errors |
| `verify` on the real container (every file hashed through PFS → PFSC → exFAT) | exit 0, all 166 723 files hashed, 1 822 s single-threaded = 88 MB/s; dominated by per-file overhead, not decoding (`raw/windows-reader-path.log`) |
| `cat` of the largest file (582 MB), single stream | 389 MB/s cold, 492 MB/s warm — above the 300 MB/s gate target, without FUSE |

Part B (Linux, BC-250 dev box, 2026-09-29). Setup as recorded in experiment 0003: Bazzite 44,
kernel 7.2.4, `fedora` distrobox (Fedora 44), Rust 1.98.1, fuse3 3.18.2, MkPFS 1.0.0 from PyPI as
oracle, `tools/` at `864a44f`, `run.sh` at the commit that measures throughput first on a fresh mount.
Work directories on the NVMe (`~/bc5-work`), removed after each run. Raw logs:
`raw/run-<preset>.log`.

| Preset | Content | Mount: tree / SHA-256 | MkPFS verify | `dd bs=1M` of the largest file, first read through a fresh mount |
| --- | --- | --- | --- | --- |
| one-small | 1 file, 12 B | OK / OK | 0 errors, 0 warnings | 12 B (latency only) |
| mixed-compress | 3 files, 0.6 MB, raw + zlib blocks | OK / OK | 0 / 0 | 256 KiB at 440 MB/s |
| noise-256m | 256 MiB incompressible (4 101 blocks, 5 compressed) | OK / OK | 0 / 0 | **1.4 GB/s** |
| sparse-1g | 1 GiB, 16 390 zlib blocks | OK / OK | 0 / 0 | **2.1 GB/s** |

Caveats: passwordless `sudo` was not available, so `drop_caches` did not run and the (just written)
container file was in the host page cache; the numbers measure PFSC decoding + exFAT + FUSE, not
the NVMe. `noise-256m` is stored raw (no inflate) and `sparse-1g` inflates zeros; inflate-heavy real
game data was measured only on Windows without FUSE (389–492 MB/s, Part A). An earlier ordering of
`run.sh` read each file for SHA-256 before `dd` and reported 5–9 GB/s from the page cache; those
numbers were discarded and the script fixed.

**Verdict.** **Passed — gate G0a.** On the BC-250, a synthetic container mounted with FUSE yields a
file tree and per-file SHA-256 identical to the source directory for every preset, an independent
implementation (MkPFS) accepts every container we generate, `cargo test` passes on Linux and
Windows, and sequential read through the mount is ≥ 1.4 GB/s, well above the 300 MB/s target.
Open for later (not gate conditions): a cold-cache, inflate-heavy measurement on the BC-250 with a
real container, and a FUSE mount of the maintainer's own dump there.
