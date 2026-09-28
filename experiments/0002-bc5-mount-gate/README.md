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

Part B (Linux): not run yet.

**Verdict.** Pending. The reader path passes every check on Windows, including a real 47.5 GB
container, and single-stream throughput clears the gate target before FUSE overhead; the gate itself
(FUSE mount tree/hash equality and ≥ 300 MB/s through the mount) needs the Linux run of `run.sh`.
Record its `raw/run.log` here and write the verdict then; if the numbers come from a later date, add
them as experiment 0003 instead of editing this one.
