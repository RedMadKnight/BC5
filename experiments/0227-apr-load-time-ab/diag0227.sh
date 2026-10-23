#!/usr/bin/env bash
# BC5 experiment 0227: the disk under the slow startup reads, read-only except for one 2-GB test file in this
# experiment's directory, which is deleted at the end. Under its own BOX-LOCK line; no emulator.
#   1. The NVMe's state without root: model, PCIe link speed and width, temperature (hwmon), and smartctl / nvme smart-log
#      if they run unprivileged.
#   2. O_DIRECT reads of the ASTRO BOT image, 1 GiB each at 0, 12 and 30 GiB, and 12 GiB again.
#   3. A fresh 2-GiB file (dd from /dev/urandom, conv=fsync), the page cache dropped, read back with O_DIRECT, 1 GiB at
#      0 and 1 GiB: budget drives may read old, cold data slower than fresh data.
# usage: diag0227.sh > raw/diag-<time>.txt   (on the box)
set -u
E=$HOME/bc5-work/exp0227; LOCK=$HOME/bc5-work/BOX-LOCK
C="$HOME/bc5-data/games/PPSA21567 - ASTRO BOT_4xx.ffpfsc"
F=$E/fresh-2g.bin
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "locked: $(cat "$LOCK")"; exit 1; }
echo "exp 0227 | disk diagnosis: NVMe state, O_DIRECT reads of the ASTRO image, a 2-GB fresh-file test (written and deleted in exp0227), no emulator (Go from the top session) | start $(date +%H:%M) | until ~$(date -d +6min +%H:%M)" > "$LOCK"
release() { grep -q "^exp 0227 | disk diagnosis" "$LOCK" 2> /dev/null && rm -f "$LOCK"; }
trap 'rm -f "$F"; release' EXIT
echo "== $(date '+%F %T') boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"
D=$(readlink -f /sys/class/nvme/nvme0/device)
echo "== NVMe: model '$(cat /sys/class/nvme/nvme0/model 2> /dev/null | xargs)', firmware $(cat /sys/class/nvme/nvme0/firmware_rev 2> /dev/null | xargs), PCI $D"
echo "   link $(cat "$D/current_link_speed" 2> /dev/null) x$(cat "$D/current_link_width" 2> /dev/null) (max $(cat "$D/max_link_speed" 2> /dev/null) x$(cat "$D/max_link_width" 2> /dev/null))"
for h in "$D"/hwmon/hwmon*/temp*_input; do [ -r "$h" ] && echo "   $(basename "$h") $(( $(cat "$h") / 1000 )) C ($(cat "${h%_input}_label" 2> /dev/null))"; done
echo "   scheduler $(cat /sys/block/nvme0n1/queue/scheduler), read_ahead_kb $(cat /sys/block/nvme0n1/queue/read_ahead_kb)"
smartctl -a /dev/nvme0 2>&1 | grep -iE "temperature|percentage used|available spare|thermal|critical warning|data units read|media and data integrity|error information|permission|denied|power on hours" | head -16
nvme smart-log /dev/nvme0 2>&1 | head -24
df -h ~ | tail -1
echo "== O_DIRECT reads of the ASTRO image (47.5 GB), 1 GiB each"
for skip in 0 3072 7680 3072; do
  printf "   at %2d GiB: " $((skip * 4 / 1024)); ionice -c2 -n7 dd if="$C" of=/dev/null bs=4M count=256 skip=$skip iflag=direct 2>&1 | tail -1
done
echo "== fresh 2-GiB file: write (urandom, fsync), drop the page cache, read back O_DIRECT"
dd if=/dev/urandom of="$F" bs=4M count=512 conv=fsync 2>&1 | tail -1
sync; echo 3 | sudo -n tee /proc/sys/vm/drop_caches > /dev/null && echo "   page cache dropped"
for skip in 0 256; do
  printf "   at %d GiB: " $((skip * 4 / 1024)); ionice -c2 -n7 dd if="$F" of=/dev/null bs=4M count=256 skip=$skip iflag=direct 2>&1 | tail -1
done
echo "   filefrag: $(filefrag "$F" 2> /dev/null | sed 's/.*: //')"
rm -f "$F" && echo "   test file deleted"
df -h ~ | tail -1
echo "== $(date +%T) done"
