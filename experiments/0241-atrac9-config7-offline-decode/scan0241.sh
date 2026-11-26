#!/usr/bin/env bash
# BC5 experiment 0241, step 1: mount the second title's package read-only (no disk cache) under a BOX-LOCK line of the
# top session, copy its Wwise ATRAC9 streams to ~/bc5-data/priv/exp0241/streams (mode 700, never committed) with
# find0241.py, unmount, release the lock. No emulator, no GPU work. Run on the box: nohup setsid ./scan0241.sh &
set -u
E=$HOME/bc5-work/exp0241; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; P=$HOME/bc5-data/priv/exp0241
M=$HOME/bc5-data/mnt/exp0241; BM=$HOME/bc5-work/bc5-tools-ubuntu/release/bc5-mount
PKG=$HOME/bc5-data/pkg/game.pkg
mkdir -p "$R" "$M"; mkdir -p -m 700 "$P"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")" > "$R/scan.out"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs" > "$R/scan.out"; exit 1; }
echo "top session | exp 0241 ATRAC9 streams: read-only package mount + scan, no emulator | start $(date +%H:%M) | until ~$(date -d +30min +%H:%M)" > "$LOCK"
{
  echo "== $(date +%T) mount"
  distrobox enter ubuntu -- bash -c "
    env -u BC5_MOUNT_DISK_CACHE '$BM' mount '$PKG' '$M' > '$R/mount.log' 2>&1 &
    MP=\$!
    for _ in \$(seq 1 300); do mountpoint -q '$M' && break; sleep 0.2; done
    mountpoint -q '$M' || { echo 'mount failed'; exit 1; }
    echo '== audio-like files (size, path)'
    find '$M' -type f \\( -iname '*.pck' -o -iname '*.bnk' -o -iname '*.wem' -o -iname '*.wsp' \\) -printf '%s %P\n' | sort -k2 | tee '$R/audio-files.txt' | wc -l
    echo '== $(date +%T) scan'
    nice -n 19 ionice -c3 python3 -I '$E/find0241.py' '$M' '$P/streams' d/0/wem_0 d/0/wem_1 d/0/soundbank d/1/soundbank d/1/wem_0 d/1/wem_1 d/0/wem.us d/1/wem.us > '$R/index.tsv'
    echo \"scan rc \$?\"
    fusermount3 -u '$M'; wait \$MP
    echo 'unmounted'
  "
  echo "== $(date +%T) done"
} > "$R/scan.out" 2>&1
grep -q "^top session | exp 0241" "$LOCK" 2> /dev/null && rm -f "$LOCK"
