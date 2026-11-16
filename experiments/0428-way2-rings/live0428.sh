#!/usr/bin/env bash
# BC5 exp 0428: a live sampler for a silent freeze (the 16:59:45 one of 2026-11-16 left no kernel line). Run over ssh from the
# laptop with its stdout streamed there, so the last seconds before a freeze survive on the laptop. Read-only, no kill.
# One line per second:
#   time | MemAvailable, Active, Inactive, Dirty, SwapFree (MiB) | PSI memory and io some/full avg10 | the emulator's
#   pid, state, RSS (MiB), threads in D state | D-state tasks system-wide with their wchan (at most 6)
# usage (on the box): bash live0428.sh <seconds>
set -u
export LC_ALL=C
END=$(( $(date +%s) + ${1:-900} ))
mi() { awk -v k="$1:" '$1 == k {printf "%d", $2 / 1024}' /proc/meminfo; }
psi() { awk '{for (i = 1; i <= NF; i++) if ($i ~ /^avg10=/) {sub("avg10=", "", $i); printf "%s%s", (n++ ? "/" : ""), $i}}' "/proc/pressure/$1"; }
while [ "$(date +%s)" -lt "$END" ]; do
  p=$(pgrep -o '^kyty_emulator')
  e="-"
  if [ -n "$p" ] && [ -r "/proc/$p/status" ]; then
    st=$(awk '$1 == "State:" {print $2}' "/proc/$p/status")
    rss=$(awk '$1 == "VmRSS:" {printf "%d", $2 / 1024}' "/proc/$p/status")
    dth=$(grep -l '^State:.D' /proc/"$p"/task/*/status 2> /dev/null | wc -l)
    e="emu $p $st rss ${rss}M Dthreads $dth"
  fi
  dl=$(ps -eo pid,stat,wchan:24,comm --no-headers 2> /dev/null | awk '$2 ~ /^D/ {printf "%s:%s:%s ", $1, $4, $3; if (++n >= 6) exit}')
  echo "$(date +%T.%N | cut -c1-12) | avail $(mi MemAvailable) act $(mi Active) inact $(mi Inactive) dirty $(mi Dirty) swapfree $(mi SwapFree) | psi mem $(psi memory) io $(psi io) | $e | D: ${dl:-none}"
  sleep 1
done
