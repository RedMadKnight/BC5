#!/usr/bin/env bash
# BC5: full-screen screenshots every $STEP seconds from $FROM to $TO seconds after the emulator
# starts, into ~/bc5-work/shots-loop/. Run inside the ubuntu distrobox next to lle-cycle.sh.
set -u
FROM=${1:-34}; TO=${2:-62}; STEP=${3:-3}; D=~/bc5-work/shots-loop
rm -rf "$D"; mkdir -p "$D"
for _ in $(seq 1 120); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
[ -z "${PID:-}" ] && exit 1
S=$(date +%s)
sleep "$FROM"
while kill -0 "$PID" 2>/dev/null; do
  T=$(( $(date +%s) - S ))
  [ "$T" -gt "$TO" ] && break
  distrobox-host-exec spectacle -b -n -f -o "$D/t$(printf %03d $T).png" >/dev/null 2>&1 || true
  sleep "$STEP"
done
