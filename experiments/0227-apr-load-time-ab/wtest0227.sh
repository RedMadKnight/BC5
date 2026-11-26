#!/usr/bin/env bash
# BC5 experiment 0227: the drive's write speed with conv=fsync (2 GiB from /dev/urandom into this experiment's
# directory), the page cache dropped, the file read back with O_DIRECT, then deleted. Under its own BOX-LOCK line, no
# emulator. On 2026-10-23 09:34 it wrote at 14.5 MB/s with 29-31 GB free; this repeats it after space is freed.
# usage: wtest0227.sh   (on the box)
set -u
E=$HOME/bc5-work/exp0227; LOCK=$HOME/bc5-work/BOX-LOCK; F=$E/wtest-2g.bin
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "locked: $(cat "$LOCK")"; exit 1; }
echo "exp 0227 | write test: 2 GiB fsync into exp0227, read back, deleted; no emulator | start $(date +%H:%M) | until ~$(date -d +5min +%H:%M)" > "$LOCK"
trap 'rm -f "$F"; grep -q "^exp 0227 | write test" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
echo "== $(date '+%F %T'): $(df -h ~ | tail -1)"
dd if=/dev/urandom of="$F" bs=4M count=512 conv=fsync 2>&1 | tail -1
sync; echo 3 | sudo -n tee /proc/sys/vm/drop_caches > /dev/null && echo "page cache dropped"
dd if="$F" of=/dev/null bs=4M iflag=direct 2>&1 | tail -1
rm -f "$F" && echo "test file deleted; $(df -h ~ | tail -1)"
