#!/usr/bin/env bash
# BC5 exp 0401 runner, the third exp 0409 series (2026-11-09, the top's request after x9r1's silent freeze): a read-only
# stall catcher beside the arms. The runner's freeze watcher only fires when a thread burns over 90 % CPU, and x9r1 froze
# with none. For each emulator process: once its play log has "fps counter" lines and none new has come for 60 s while the
# process lives, write ONE dump: every thread's name, state and wchan (/proc, no root) and the whole process's stacks by
# eu-stack (a ptrace attach that only reads). Ends at <end epoch> or when <stop file> exists.
# usage (on the box): stall0409.sh <play log> <out dir> <end epoch> <stop file>
set -u
LOG=$1 OUT=$2 END=$3 STOP=$4
mkdir -p "$OUT"
done_pid=""
while [ "$(date +%s)" -lt "$END" ] && [ ! -e "$STOP" ]; do
  EP=$(pgrep -x kyty_emulator | head -1)
  if [ -z "$EP" ] || [ "$EP" = "$done_pid" ]; then sleep 5; continue; fi
  n1=$(grep -a -c "fps counter" "$LOG" 2> /dev/null); n1=${n1:-0}
  if [ "$n1" -eq 0 ]; then sleep 5; continue; fi
  sleep 60
  [ -d "/proc/$EP" ] || continue
  n2=$(grep -a -c "fps counter" "$LOG" 2> /dev/null); n2=${n2:-0}
  if [ "$n2" = "$n1" ]; then
    f=$OUT/stall-$EP-$(date +%H%M%S).txt
    { echo "# $(date '+%F %T') emulator $EP: no new fps counter line for 60 s ($n1 lines in $LOG)"
      for t in /proc/"$EP"/task/*; do echo "$(basename "$t") $(cat "$t/comm" 2> /dev/null) state $(awk '{print $3}' "$t/stat" 2> /dev/null) wchan $(cat "$t/wchan" 2> /dev/null)"; done
      echo "## eu-stack -p $EP"
      timeout 90 eu-stack -p "$EP" 2>&1 | head -4000
    } > "$f"
    done_pid=$EP
  fi
done
