# 0331 — bc5-mount with the kernel's readahead off for the image and its disk cache: does it hold F397's gain without the box's setting?

*Number claimed by the cloud supervisor, 2026-10-26 (the maintainer: "rób 1 i 2, a potem ja 3"; on the new dependency:
"nie szkodzi że nowa zależność - jest zgoda").*

**Question.** In the maintainer's free play bc5-mount read 78 % more from the NVMe than it asked for (F396). The cause
is the btrfs bdi readahead of 4,096 KiB on the scattered block reads of the image. With that readahead set to 128 KiB
by root at runtime, the surplus fell to 7 % and the memory stall by five sixths (F397). Can bc5-mount get the same
result by itself, with `POSIX_FADV_RANDOM` on the files it reads a block at a time? That would need no root, would not
touch the rest of the filesystem, and would survive a reboot.

**Setup.**
- **The change** (BC5 main, `feat(mount)`):
  - `tools/bc5-mount/src/io.rs` turns readahead off on every `FileSource`, that is the image, including the preload's
    own descriptor;
  - `src/pkg/diskcache.rs` does the same on the disk cache's data file (8.1 GB on the box, read with plain
    `read_exact_at`);
  - `BC5_MOUNT_READAHEAD=1` keeps the kernel's readahead, for an A/B;
  - the call is `nix::fcntl::posix_fadvise`. `nix` 0.29 with `fs` is already in the tree through `fuser`, so the
    lockfile gains one line and no crate;
  - checked here: `cargo fmt -p bc5-mount --check`, `cargo clippy -p bc5-mount --all-targets --all-features -- -D
    warnings` (and with `--no-default-features`), and `cargo test -p bc5-mount` (68 + 15 + 10 passed, 1 ignored as
    before). The new test is `io::tests::file_reads_are_unchanged_by_the_random_advice`.
- **The private build:**
  - built on the box in the `ubuntu` distrobox as `tools/scripts/bc5-build.sh` builds the shared one
    (`cargo build --release --locked -p bc5-mount`), from this tree, into `~/bc5-work/exp0331/`;
  - the shared `~/bc5-work/bc5-tools-ubuntu/release/bc5-mount` (47739557, from 2c30d05 of 10-17) is not touched;
  - this tree's bc5-mount differs from it by commit d53e575 (the startup preload, off unless `BC5_MOUNT_PRELOAD`, which
    no launcher sets) and by this change.
- **The test shortcut** "BC5 emulator (test 0330: pamięć)" gets its mount from the private build:
  - one line, `BM=`, in `~/bc5-work/exp0330/play-pkg-0330t.sh`;
  - it is otherwise as in F395–F397: the 0330 binary, the zero scan at 540 s, `sample0330p.sh` beside each session.
- **The maintainer's session (step 3):** he first puts the box's readahead back with
  `echo 4096 | sudo tee /sys/class/bdi/btrfs-1/read_ahead_kb` (or a reboot), so that the change is measured alone.

**Readings.**
- **Primary:** NVMe sectors read / bc5-mount's `rchar`. It was 1.78 with readahead 4,096 (F396) and 1.07 with 128
  (F397); expect ≤ 1.1.
- **Then, per minute, against F396 and F397:**
  - PSI memory "full";
  - file refaults;
  - flips/s;
  - MemAvailable.

**Result.** Pending.
