#!/usr/bin/env bash
# BC5 experiment 0227: every 1 s while the emulator <pid> runs, the CPU time of the bc5-mount process serving it (the
# launcher mounts the image at every start): the sum of its bc5-mount-io* read workers' schedstat run time (ns), the
# rest of its threads, and its RSS (kB). Shows whether the startup reads are bound by decoding (workers busy) or by the
# disk. Read-only. usage: bcm0227.sh <out> <emulator pid>
OUT=$1 EP=$2
M=""
for _ in $(seq 1 60); do M=$(pgrep -n -x bc5-mount) && break; sleep 0.5; done
{
  echo "# bcm0227 bc5-mount pid ${M:-none} emulator $EP start $(date '+%F %T'); columns: b uptime io_workers_ns other_ns rss_kb threads"
  [ -n "$M" ] || exit 0
  while [ -d "/proc/$EP" ] && [ -d "/proc/$M" ]; do
    io=0 other=0 n=0
    for t in /proc/"$M"/task/*; do
      c=$(cat "$t/comm" 2> /dev/null); s=$(cut -d' ' -f1 "$t/schedstat" 2> /dev/null); [ -n "$s" ] || continue
      n=$((n + 1))
      case $c in bc5-mount-io*) io=$((io + s)) ;; *) other=$((other + s)) ;; esac
    done
    echo "b $(cut -d' ' -f1 /proc/uptime) $io $other $(awk '/^VmRSS:/ {print $2}' "/proc/$M/status" 2> /dev/null) $n"
    sleep 1
  done
  echo "# bcm0227 end $(date '+%F %T')"
} >> "$OUT"
