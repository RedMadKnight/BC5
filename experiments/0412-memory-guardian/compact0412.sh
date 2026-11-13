#!/usr/bin/env bash
# BC5 exp 0412 (README section 58): who drives kcompactd during a run. Read-only: /proc/vmstat, /proc/buddyinfo,
# /proc/<kcompactd0, kswapd0>/stat, /proc/sys/vm/compaction_proactiveness. No setting is changed, nothing needs root.
# One line every INTERVAL seconds until the process pid:<n> is gone, or for <seconds>:
#   t s | kcompactd0 and kswapd0 CPU (s since the collector's start) | the compaction counters as deltas since the
#   start | free blocks of order 9 and 10 (all zones) | MemAvailable MiB
# How to read it (section 58): (i) proactive compaction shows as kcompactd CPU and compact_daemon_*_scanned growing
#   while kswapd is idle (pageoutrun flat) and compact_daemon_wake flat; (ii) kswapd-driven compaction as
#   compact_daemon_wake growing with pageoutrun; (iii) our high-order requests as compact_stall / compact_fail (direct
#   compaction in the allocating thread) and allocstall growing.
# usage: compact0412.sh <out file> <interval s> [pid:<emulator pid> | <seconds>]
set -u
export LC_ALL=C
OUT=${1:?an output file}; INT=${2:-5}; ARG=${3:-60}
KC=$(pgrep -x kcompactd0 | head -1); KS=$(pgrep -x kswapd0 | head -1)
cpu() { [ -n "$1" ] && awk '{print $14 + $15}' "/proc/$1/stat" 2> /dev/null || echo 0; }
KEYS="compact_daemon_wake compact_daemon_migrate_scanned compact_daemon_free_scanned compact_stall compact_fail compact_success compact_migrate_scanned compact_free_scanned compact_isolated pgmigrate_success pgmigrate_fail pageoutrun allocstall_normal allocstall_movable kswapd_low_wmark_hit_quickly kswapd_high_wmark_hit_quickly thp_fault_alloc thp_collapse_alloc"
snap() { awk -v keys="$KEYS" 'BEGIN {n = split(keys, k, " ")} {v[$1] = $2} END {for (i = 1; i <= n; i++) printf "%s ", (k[i] in v) ? v[k[i]] : "-"}' /proc/vmstat; }
buddy() { awk '{o9 += $(NF - 1); o10 += $NF} END {printf "%d %d", o9, o10}' /proc/buddyinfo; }
read -r -a B0 <<< "$(snap)"
C0=$(cpu "$KC"); S0=$(cpu "$KS"); T0=$(date +%s)
{
  echo "# $(date '+%F %T') compaction collector, every $INT s; kcompactd0 pid ${KC:-none}, kswapd0 pid ${KS:-none}; compaction_proactiveness $(cat /proc/sys/vm/compaction_proactiveness 2> /dev/null), extfrag_threshold $(cat /proc/sys/vm/extfrag_threshold 2> /dev/null); thp $(cat /sys/kernel/mm/transparent_hugepage/enabled 2> /dev/null); uptime $(awk '{printf "%.1f h", $1 / 3600}' /proc/uptime)"
  echo "# buddyinfo at the start:"; sed 's/^/#   /' /proc/buddyinfo
  echo "# t | kcompactd_s kswapd_s | $KEYS (deltas) | free_order9 free_order10 | avail_MiB"
} > "$OUT"
while :; do
  NOW=$(($(date +%s) - T0))
  case "$ARG" in
    pid:*) [ -d "/proc/${ARG#pid:}" ] || LAST=1 ;;
    *[!0-9]* | "") LAST=1 ;;
    *) [ "$NOW" -lt "$ARG" ] || LAST=1 ;;
  esac
  read -r -a B <<< "$(snap)"
  D=""; for i in "${!B[@]}"; do if [ "${B[$i]}" = "-" ]; then D="$D - "; else D="$D $((B[i] - B0[i]))"; fi; done
  echo "$NOW | $(( ($(cpu "$KC") - C0) / 100 )) $(( ($(cpu "$KS") - S0) / 100 )) |$D | $(buddy) | $(awk '/^MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)" >> "$OUT"
  [ "${LAST:-0}" = 1 ] && break
  sleep "$INT"
done
{ echo "# buddyinfo at the end:"; sed 's/^/#   /' /proc/buddyinfo; echo "# end $(date '+%F %T')"; } >> "$OUT"
