#!/usr/bin/env bash
# BC5 experiment 0033: parallel sequential reads through bc5-mount, N read workers vs 1.
# usage: mount-bench.sh <bc5-mount binary> <container> <mountpoint> <readers> <MiB each> <worker counts...>
set -u
BM=$1; C=$2; M=$3; READERS=$4; MIB=$5; shift 5
mkdir -p "$M"
mountpoint -q "$M" && fusermount3 -u "$M"
for W in "$@"; do
  sync; sudo -n sh -c 'echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null || echo "(drop_caches unavailable)"
  (BC5_MOUNT_THREADS=$W setsid "$BM" mount "$C" "$M" < /dev/null > /tmp/bench-mount.log 2>&1 &)
  for _ in $(seq 1 50); do mountpoint -q "$M" && break; sleep 0.1; done
  # the largest files, each read from its start
  mapfile -t FILES < <(find "$M" -type f -printf '%s %p\n' | sort -rn | head -"$READERS" | cut -d' ' -f2-)
  PID=$(pgrep -n -x bc5-mount)
  T0=$(date +%s.%N)
  DDS=()
  for f in "${FILES[@]}"; do dd if="$f" of=/dev/null bs=1M count="$MIB" status=none & DDS+=($!); done
  wait "${DDS[@]}"
  T1=$(date +%s.%N)
  THREADS=$(ls /proc/"$PID"/task | wc -l)
  echo "workers $W ($(head -1 /tmp/bench-mount.log)), $THREADS threads: ${#FILES[@]} readers x $MIB MiB in $(echo "$T1 - $T0" | bc) s = $(echo "${#FILES[@]} * $MIB / ($T1 - $T0)" | bc) MiB/s"
  fusermount3 -u "$M"; sleep 1
done
