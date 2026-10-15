#!/bin/bash
# FUSE: one mount per run, 8 parallel dd readers of different files plus 4 dd
# readers of one of them, old binary vs new (and the new one with 16 or 64 MiB
# caches; NFILES, ROUNDS, VARIANTS select the runs). Prints wall seconds, the mount's CPU seconds, the decode counter
# right after the open, and the last stats line.
set -u
export LC_ALL=C
. "$(dirname "$0")/bench-common.sh"
pick_files
mapfile -t FILES < "$W/files.txt"
mkdir -p "$MNT"
TICK=$(getconf CLK_TCK)
ROUNDS=${ROUNDS:-3}
VARIANTS=${VARIANTS:-"old new new16"}

cpu_of() { awk -v t="$TICK" '{printf "%.2f", ($14 + $15) / t}' "/proc/$1/stat"; }

one_run() { # label binary cache_mib(or empty)
    local label=$1 bin=$2 mib=$3
    mountpoint -q "$MNT" && fusermount3 -u "$MNT"
    if [ -n "$mib" ]; then
        BC5_MOUNT_STATS=0.5 BC5_MOUNT_CACHE_MIB=$mib "$bin" mount "$DUMP" "$MNT" 2> "$W/mount-$label.log" &
    else
        BC5_MOUNT_STATS=0.5 "$bin" mount "$DUMP" "$MNT" 2> "$W/mount-$label.log" &
    fi
    local pid=$!
    for _ in $(seq 100); do mountpoint -q "$MNT" && break; sleep 0.1; done
    mountpoint -q "$MNT" || { echo "$label: mount failed"; cat "$W/mount-$label.log"; return; }
    sleep 1.2 # the stats line for the open itself
    local opened
    opened=$(grep stats "$W/mount-$label.log" | tail -1 | grep -o 'decoded [0-9]* blocks')
    local c0 t0 t1 c1
    c0=$(cpu_of $pid); t0=$(date +%s.%N)
    local pids=()
    for f in "${FILES[@]}"; do dd if="$MNT/$f" of=/dev/null bs=1M status=none & pids+=($!); done
    for i in 1 2 3 4; do dd if="$MNT/${FILES[1]}" of=/dev/null bs=1M status=none & pids+=($!); done
    wait "${pids[@]}"
    t1=$(date +%s.%N); c1=$(cpu_of $pid)
    sleep 0.7
    fusermount3 -u "$MNT"; wait $pid 2>/dev/null
    printf '%-8s wall %5.2f s  mount cpu %5.2f s | at open: %s | %s\n' "$label" \
        "$(awk "BEGIN{print $t1 - $t0}")" "$(awk "BEGIN{print $c1 - $c0}")" "${opened:-none}" \
        "$(grep stats "$W/mount-$label.log" | tail -1 | sed 's/^bc5-mount stats //; s/, from disk.*//')"
}

for round in $(seq "$ROUNDS"); do
    for v in $VARIANTS; do
        pgrep -x kyty_emulator >/dev/null && { echo "a game started; stopping"; exit 1; }
        case $v in
            old) one_run "old-$round" "$OLD" "" ;;
            new) one_run "new-$round" "$NEW" "" ;;
            new16) one_run "new16-$round" "$NEW" 16 ;;
            new64) one_run "new64-$round" "$NEW" 64 ;;
        esac
    done
done
