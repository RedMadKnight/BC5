#!/usr/bin/env bash
# BC5 exp 0412: a series of night arms (run0412n.sh), one after another, on the box under setsid nohup so it does not
# depend on the laptop's ssh. Tags are <prefix><n><arm>. Between arms it waits until no emulator runs and the box has
# 9 GiB available again (up to 120 s). It stops before the next arm when the last one ended with a failed GPU reset,
# when the box does not recover, when a file $N/STOP exists, or when the clock passes N_UNTIL (HHMM, default 0150).
# usage (on the box): series0412n.sh <prefix> <play s> <arm> [<arm> ...]
set -u
export LC_ALL=C
X=$HOME/bc5-work/exp0412; N=$X/night; R=$N/raw
P=${1:?a prefix}; PLAY=${2:?the play seconds}; shift 2
case "$P" in *[!A-Za-z]* | "") echo "the prefix is letters"; exit 1 ;; esac
UNTIL=${N_UNTIL:-0150}
late() { local h; h=$(date +%H%M); [ "$UNTIL" -lt 1200 ] && [ "$h" -lt 1200 ] && [ "$h" -ge "$UNTIL" ]; }
i=0
for ARM in "$@"; do
  i=$((i + 1)); TAG="$P$i$(printf '%s' "$ARM" | tr -cd 'A-Za-z0-9')"
  [ -e "$N/STOP" ] && { echo "$(date '+%F %T') series $P: STOP file, ending before $TAG"; break; }
  late && { echo "$(date '+%F %T') series $P: past $UNTIL, ending before $TAG"; break; }
  ok=0
  for _ in $(seq 1 24); do
    a=$(awk '/^MemAvailable:/ { print int($2 / 1024) }' /proc/meminfo)
    if ! pgrep '^kyty_emulator' > /dev/null && [ "$a" -ge 9000 ]; then ok=1; break; fi
    sleep 5
  done
  [ "$ok" = 1 ] || { echo "$(date '+%F %T') series $P: the box did not recover ($a MiB available, emulator $(pgrep -c '^kyty_emulator')), ending before $TAG"; break; }
  echo "$(date '+%F %T') series $P: $TAG starts ($a MiB available)"
  bash "$X/run0412n.sh" "$TAG" "$ARM" "$PLAY" 2>&1 | tail -3
  grep -q "GPU HANG: reset failed" "$R/$TAG-end.txt" 2> /dev/null && { echo "$(date '+%F %T') series $P: a failed GPU reset, ending"; break; }
  sleep 10
done
echo "$(date '+%F %T') series $P: end"
