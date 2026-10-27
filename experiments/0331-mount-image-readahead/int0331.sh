#!/usr/bin/env bash
# BC5 experiment 0331: the integration of the tested bc5-mount (43277724, BC5 main fda1c01: the kernel's readahead off for
# the image and the disk cache's data file, F398) into the shared ~/bc5-work/bc5-tools-ubuntu/release/bc5-mount
# (47739557, from 2c30d05), on the maintainer's yes ("c", 2026-10-26). The binary that ran in his two test sessions is the
# one installed: same toolchain and flags as tools/scripts/bc5-build.sh's mount step (cargo build --release --locked).
# Every launcher that names the shared mount takes it, ASTRO BOT's play-astro.sh too (its .ffpfsc image; not tested there;
# BC5_MOUNT_READAHEAD=1 in a launcher keeps the old readahead).
# Guards: no emulator, launcher or bc5-mount; an empty lock; both md5s. A lock line with an EXIT trap that clears only that
# line. The old binary is kept in ~/bc5-work/exp0331/integration/. The install is a rename in the same directory, so a
# reader sees the old file or the new one, never half of one. After it: the md5, --help and an inspect of the second
# title's package, both in the distrobox.
# usage: int0331.sh   (on the box)
set -u
W=$HOME/bc5-work; E=$W/exp0331; I=$E/integration; R=$E/raw; LOCK=$W/BOX-LOCK
S=$W/bc5-tools-ubuntu/release/bc5-mount; P=$E/bc5-mount; PKG=$HOME/bc5-data/pkg/game.pkg
md5() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
ps -eo args= | grep -qE '^(/[^ ]*/)?bash [^ ]*/(play-[^ ]*|run-[^ ]*|test0330p)\.sh( |$)' && { echo "a launcher runs: stop"; exit 1; }
pgrep -x bc5-mount > /dev/null && { echo "a bc5-mount runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5 "$S")" = 47739557 ] || { echo "the shared mount is not 47739557: stop"; exit 1; }
[ "$(md5 "$P")" = 43277724 ] || { echo "the tested mount is not 43277724: stop"; exit 1; }
[ -e "$I" ] && { echo "$I exists: stop"; exit 1; }
echo "cloud exp 0331 | integration of the tested bc5-mount into the shared one (no emulator) | start $(date +%H:%M) | until ~$(date -d +5min +%H:%M)" > "$LOCK"
trap 'grep -q "^cloud exp 0331 | integration" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
mkdir -p "$I" "$R" || exit 1
cp -p "$S" "$I/bc5-mount.47739557" && [ "$(md5 "$I/bc5-mount.47739557")" = 47739557 ] || { echo "the backup failed: stop"; exit 1; }
restore() { cp -p "$I/bc5-mount.47739557" "$S.restore-0331" && mv -f "$S.restore-0331" "$S"; echo "RESTORED: $(md5 "$S")"; exit 1; }
cp -p "$P" "$S.new-0331" && mv -f "$S.new-0331" "$S" || restore
[ "$(md5 "$S")" = 43277724 ] || { echo "the installed mount is not 43277724"; restore; }
distrobox enter ubuntu -- "$S" --help > /dev/null 2>&1 || { echo "the installed mount does not run"; restore; }
distrobox enter ubuntu -- timeout 60 "$S" inspect "$PKG" > "$R/int-inspect.txt" 2>&1 || { echo "inspect failed (raw/int-inspect.txt)"; restore; }
echo "shared bc5-mount: 47739557 -> $(md5 "$S"); inspect of the package: $(wc -l < "$R/int-inspect.txt") lines"
echo "undo: cp -p $I/bc5-mount.47739557 $S.undo && mv -f $S.undo $S"
