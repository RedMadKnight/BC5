#!/usr/bin/env bash
# BC5 (experiment 0175): once a second while the emulator runs, the kernel's memory-pressure
# counters as deltas — direct reclaim stalls, direct compaction stalls, swap in/out, major faults,
# pages scanned by direct reclaim — with MemAvailable, keyed by the seconds since the emulator
# process started (the same origin as the host's process-time "t" of the fps and audio lines).
# usage: vmstat-sampler.sh <out> [max seconds]
set -u
OUT=$1; MAX=${2:-7200}
: > "$OUT"
for _ in $(seq 1 300); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
[ -z "${PID:-}" ] && { echo "no emulator" >> "$OUT"; exit 1; }
HZ=$(getconf CLK_TCK); BT=$(awk '/^btime/{print $2}' /proc/stat)
ST=$(awk '{print $22}' /proc/$PID/stat); START=$(( BT * 100 + ST * 100 / HZ )) # centiseconds since epoch
read_vm() { awk '/^(allocstall_normal|allocstall_movable|compact_stall|pswpin|pswpout|pgmajfault|pgscan_direct|pgsteal_direct) /{v[$1]=$2} END{print v["allocstall_normal"]+v["allocstall_movable"], v["compact_stall"], v["pswpin"], v["pswpout"], v["pgmajfault"], v["pgscan_direct"], v["pgsteal_direct"]}' /proc/vmstat; }
set -- $(read_vm); p_as=$1 p_cs=$2 p_si=$3 p_so=$4 p_mf=$5 p_sd=$6 p_st=$7
for i in $(seq 1 "$MAX"); do
  sleep 1
  kill -0 "$PID" 2>/dev/null || break
  set -- $(read_vm)
  now=$(( $(date +%s%N) / 10000000 ))
  t=$(awk -v n=$now -v s=$START 'BEGIN{printf "%.1f", (n - s) / 100}')
  ma=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  echo "vm: t $t s: reclaim stalls $(( $1 - p_as )), compaction stalls $(( $2 - p_cs )), swap in $(( $3 - p_si )) out $(( $4 - p_so )) pages, major faults $(( $5 - p_mf )), direct scan $(( $6 - p_sd )) steal $(( $7 - p_st )), MemAvailable $ma MiB" >> "$OUT"
  p_as=$1 p_cs=$2 p_si=$3 p_so=$4 p_mf=$5 p_sd=$6 p_st=$7
done
echo DONE >> "$OUT"
