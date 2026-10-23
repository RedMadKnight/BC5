#!/usr/bin/env bash
# BC5 experiment 0229: every 0.5 s while the emulator <pid> runs, its cumulative counters from /proc/<pid>/io: rchar
# (bytes returned by read(), FUSE included), read_bytes (from the block layer), wchar and write_bytes (the journal's
# writes, for the capture hypothesis of 2026-10-23). Load bursts show as steep stretches; the load-time A/B compares
# when they end. Read-only. usage: io0229.sh <out> <pid>
OUT=$1 P=$2
{
  echo "# io0229 pid $P start $(date '+%F %T') uptime $(cut -d' ' -f1 /proc/uptime); columns: i uptime rchar read_bytes wchar write_bytes"
  while [ -d "/proc/$P" ]; do
    echo "i $(cut -d' ' -f1 /proc/uptime) $(awk '$1 == "rchar:" {r = $2} $1 == "read_bytes:" {b = $2} $1 == "wchar:" {w = $2} $1 == "write_bytes:" {x = $2} END {print r + 0, b + 0, w + 0, x + 0}' "/proc/$P/io" 2> /dev/null)"
    sleep 0.5
  done
  echo "# io0229 end $(date '+%F %T')"
} >> "$OUT"
