# bc5-compress-captures

Daily lossless compression of the emulator's capture journals on the maintainer's box.

Every play run writes `~/bc5-data/captures/play-<date>-<time>/` (`PLAY_CAPTURE=1`), whose
`gc/direct.log` and `guest-printf.txt` are often 1-5 GB. By 2026-10-23 they had filled the box's
DRAM-less NVMe to 94 %. At that fill, fsync'd writes ran at 14.5 MB/s and level loads slowed down.
Compressing the old journals (136.5 GB → 6.3 GB) brought writes back to 277 MB/s
(experiment 0227).

`compress-old-captures.sh` compresses every file over 10 MB that is older than two days with
`zstd -3`, tests each archive before it removes the original, and stops on the first failure. It
skips the day if the box is busy (a `~/bc5-work/BOX-LOCK` line or a running emulator) and stops if
an emulator starts. `zstd -d file.zst` restores any journal.

Install on the box (user units, no root):

    cp compress-old-captures.sh ~/bc5-work/ && chmod +x ~/bc5-work/compress-old-captures.sh
    cp bc5-compress-captures.service bc5-compress-captures.timer ~/.config/systemd/user/
    systemctl --user daemon-reload && systemctl --user enable --now bc5-compress-captures.timer

The log is `~/bc5-work/compress-captures.log`.
