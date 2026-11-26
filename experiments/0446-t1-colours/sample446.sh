#!/usr/bin/env bash
# exp 0446: per-second I/O and memory samples during a run (read-only). usage: sample446.sh <out file> <seconds>
out=$1; n=$2; st=$(date +%s)
echo "# start $(date '+%F %T'); /var/home free $(df -B1M --output=avail /var/home | tail -1 | tr -d ' ') MiB; bc5-archive-1125b $(systemctl --user is-active bc5-archive-1125b 2> /dev/null)" > "$out"
echo "# el io_some_avg10 io_full_avg10 mount_read_MiB mount_rate_MiBs mount_rss_MiB emu_read_MiB avail_MiB archive" >> "$out"
prev=0
while [ $(( $(date +%s) - st )) -lt "$n" ]; do
    el=$(( $(date +%s) - st ))
    read -r s f < <(awk '/^some/ {split($2,a,"=")} /^full/ {split($2,b,"=")} END {print a[2], b[2]}' /proc/pressure/io)
    mp=$(pgrep -x bc5-mount | head -1); ep=$(pgrep -x kyty_emulator | head -1)
    mr=0; rss=0; er=0
    [ -n "$mp" ] && { mr=$(awk '/^read_bytes/ {print int($2 / 1048576)}' /proc/$mp/io 2> /dev/null); rss=$(awk '/VmRSS/ {print int($2 / 1024)}' /proc/$mp/status 2> /dev/null); }
    [ -n "$ep" ] && er=$(awk '/^rchar/ {print int($2 / 1048576)}' /proc/$ep/io 2> /dev/null)
    a=$(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
    echo "$el $s $f ${mr:-0} $(( ${mr:-0} - prev )) ${rss:-0} ${er:-0} $a $(systemctl --user is-active bc5-archive-1125b 2> /dev/null)" >> "$out"
    prev=${mr:-0}
    sleep 1
done
