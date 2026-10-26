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

**Built (2026-10-26 12:13).**
- `build0331.sh` built bc5-mount in the distrobox (rustc 1.93.1, offline, 26 s; `raw/build.out`) into
  `~/bc5-work/exp0331/bc5-mount`, 43277724. The shared one (47739557) was not touched.
- The test launcher's `BM=` now names it: `play-pkg-0330t.sh` bf4f3da3 → 38cefa13 (`raw/play-pkg-0330t-bm.diff`).
- **The advice is made.** Under `strace`, `bc5-mount inspect` on the image calls `fadvise64(3, 0, 0, POSIX_FADV_RANDOM) = 0`,
  and makes no such call with `BC5_MOUNT_READAHEAD=1` (`raw/strace-fadvise.txt`).
- Undo: `cat ~/bc5-work/exp0331/play-pkg-0330t.sh.before-0331 > ~/bc5-work/exp0330/play-pkg-0330t.sh`.

**Result** (2026-10-26, the maintainer's two sessions on the test shortcut).
- **Setup:**
  - he first put the box's readahead back with `echo 4096 | sudo tee /sys/class/bdi/btrfs-1/read_ahead_kb`; it read
    4096 afterwards;
  - the sessions were 12:16:34–12:20:35 and 12:20:37–12:22:07;
  - evidence in `raw/maintainer-test/`: both sampler files, the probe lines, the kernel lines and the devcoredump list.
- **Both sessions froze at the same place in the game** (t ≈ 212 s and ≈ 62 s), and he closed the emulator (exit 0):
  - gfx_0.0.0 timeouts at 12:20:11, 12:21:44 and 12:21:46, each reset succeeded;
  - devcoredumps `20261026-122011-devcd2.txt`, `-122144-devcd3.txt`, `-122146-devcd4.txt`;
  - the probe's waits are those of F395's freeze at 10:08, which ran on the shared mount, so the mount is not their
    cause (F399).
- **Mount and launcher:** none were left after the sessions, and nothing was mounted.

| | the shared mount, readahead 4,096 (F396) | the shared mount, 128 (F397) | **0331's mount, 4,096** (S1 / S2) |
|---|---|---|---|
| session | 194 s | 691 s | 233 s / 81 s |
| NVMe read / bc5-mount asked | 1.80 | 1.07 | **0.99 / 0.93** |
| NVMe rate | 190 MB/s | 92 MB/s | 98 / 126 MB/s |
| the emulator's reads | 66 MB/s | 92 MB/s | 67 / 85 MB/s |
| PSI "full" per minute | 1.71 s | 0.29 s | 0.45 / 0.49 s |
| file refaults per minute | 409 k | 119 k | 120 k / 226 k |

The ratios are deltas over the session (`sample0330p.sh`). S2 is 81 s of mostly loading. The zero scan (540 s) was not
reached.

**Verdict.**
- **The change holds F397's gain without the box's setting.** With the box's readahead at 4,096, bc5-mount read no more
  from the NVMe than it asked for (0.93–0.99, against 1.80 with the shared mount). The memory stall per minute was a
  quarter of F396's.
- **Next:** integrate it into the shared mount (`~/bc5-work/bc5-tools-ubuntu/release/bc5-mount`) on the maintainer's
  yes (D19). After that the box's readahead can stay at its default.
- **The freeze these sessions met is not the mount's.** It is F395's, now reproducible from his save in about a minute
  (F399).

**Addendum (2026-10-26 ~13:00, the integration).** On the maintainer's yes ("c"), `int0331.sh` installs the tested binary
43277724 as the shared `~/bc5-work/bc5-tools-ubuntu/release/bc5-mount` (47739557).
- **How it does it:** the guards, a lock line, a backup in `exp0331/integration/`, an atomic rename, then `--help` and
  an `inspect` of the package in the distrobox, with a restore on any failure. It was tried on stand-ins, including
  its restore path.
- **Who it affects:** every launcher that names the shared mount, ASTRO BOT's `play-astro.sh` too. That one is not
  tested; `BC5_MOUNT_READAHEAD=1` keeps the old readahead.
- **Not run by the cloud session:** its permission classifier refused the change to the shared binary ("Modify Shared
  Resources"). The script is in `~/bc5-work/exp0331/int0331.sh` (cd407ec5) for the maintainer to run.

**Addendum (2026-10-26 13:30, a correction).** The maintainer's two sessions here ran with **RT on**: his `input.cfg`
has `RayTracing.PPSA03671=on` since 10-26 00:04, and the journals have no RT-off drop line. The readahead result (F398)
does not depend on it, since both sides of the comparison are his RT-on play. The freeze (F399) came with RT on.

**Addendum (2026-10-26 14:30, integrated).** The maintainer ran `int0331.sh` himself on the box (`raw/int.out`, his
paste). The shared `~/bc5-work/bc5-tools-ubuntu/release/bc5-mount` is now 43277724 (was 47739557).
- **Checks:** the script's `inspect` of the package ran (11 lines). Its output stays on the box
  (`exp0331/raw/int-inspect.txt`), because it names the title.
- **Undo:** the backup is `exp0331/integration/bc5-mount.47739557`; the undo command is the last line of `raw/int.out`.
- **What follows:** every launcher that names the shared mount now runs with readahead off for the image and the disk
  cache, ASTRO BOT's too. The box's btrfs readahead stays at its default 4,096 KiB.
- **The test shortcut's launcher** still names `exp0331/bc5-mount`, which is the same binary.

**Addendum (2026-10-26 15:10, a 35-minute session with RT off, F400–F401).** The maintainer switched RT off in
`input.cfg` (14:31:17) and played 14:31:09–15:06:24 on the test shortcut, which uses the integrated mount. Evidence is
in `raw/maintainer-test-2/`.
- **No GPU timeout in 35 minutes.**
  - The journal has 19,558 RT-off drop lines and no TIMEOUT. There is no kernel GPU line and no devcoredump.
  - The flips per minute (`flips-per-min.txt`) were 37–46/s for most of minutes 14–27, and 20–30/s elsewhere.
- **The mount holds over a long session:** NVMe/asked 0.99, NVMe 91 MB/s, PSI "full" 0.41 s per minute (14.6 s in
  all, 5.6 s of it in the last minutes).
- **Memory:** MemAvailable after 3 min had a median of 388 MiB (min 274), and GTT grew from 12.19 to 12.51 GB. Swap
  held ~0.75–0.99 GB, with 2.2 GB swapped out over the session.
- **The zero scan at 540 s** (`zeroscan.txt`): 3,608 MiB in all-zero 2 MiB chunks, of which 1,360 in
  CommitIABufferAllocator and 1,258 in RenderGpuWcLarge.
- **The end.** His character died and the title crashed: `Access violation: Write [0x26]` at `eboot.bin+0x3ba1bdf`
  (`and byte [r10+0x26], 0xfe` with r10 = 0), exit 65 (`crash-context.txt`). The crash dump's most recent stubbed
  imports are four of the unnamed NpCppWebApi NIDs.
- **The KDE session did not log out.** KDE's screen locker came up at 15:06:34, when the emulator left; kwin_wayland and
  plasmashell ran on from 00:03. The kernel logged two `Unsupported screen format RA24` lines at that moment.
