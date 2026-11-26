# Sent to bc250 on stdin (bash -s); nothing is written on the box. Follows the newest play journal
# (~/bc5-data/captures/play-*/gc/direct.log), switching when a newer session starts, and prints only
# its timeout / fault / reopen lines, each prefixed with the box's clock. Read-only: tail of new data.
trap 'kill 0' EXIT HUP TERM
cur=""; sp=""
while true; do
  d=$(ls -1td ~/bc5-data/captures/play-*/gc 2>/dev/null | head -1)
  f="$d/direct.log"
  if [ -n "$d" ] && [ -f "$f" ] && [ "$f" != "$cur" ]; then
    [ -n "$sp" ] && kill "$sp" 2>/dev/null
    cur=$f
    echo "# $(date +%T) following $cur"
    sleep infinity & sp=$!
    tail -n0 -F --pid="$sp" "$cur" 2>/dev/null |
      grep --line-buffered -E 'TIMEOUT|^timeout|fault|^reopen|FAILED rc -|machine|GIVEN UP after [0-9]{4}' |
      while IFS= read -r l; do printf '%s %s\n' "$(date +%T)" "${l:0:400}"; done &
  fi
  sleep 10
done
