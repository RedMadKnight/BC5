#!/usr/bin/env bash
# exp 0360 laptop helper: wait (attended, up to ~40 min) until the box is free, then start one run0360.sh run there and
# a kernel stream that ends once the run's own lock line ("exp 0360 | s6n run") is gone.
# usage: go0360.sh <tag> <secs> <stream file> <pre command, run in exp0360 after the guard, or -> -- <env assignments for run0360.sh ...>
set -u
TAG=$1; SECS=$2; STREAM=$3; PRE=$4; shift 5
[ "$PRE" = - ] && PRE=true
ENVS="$*"
for i in $(seq 1 120); do
  r=$(timeout 30 ssh -n bc250 'pgrep "^kyty_emulator" >/dev/null && { echo EMU; exit 0; }; [ -s ~/bc5-work/BOX-LOCK ] && { echo LOCK; exit 0; }; echo FREE' 2>&1)
  [ "$r" = FREE ] && break
  sleep 20
done
[ "$r" = FREE ] || { echo "the box never came free"; exit 1; }
echo "$(date +%T) box free, starting $TAG"
( timeout $((SECS + 600)) ssh -n bc250 'timeout '"$((SECS + 500))"' journalctl -k -f -n 0 -o short-precise & JP=$!; sleep 20; while grep -q "^exp 0360 | s6n run" ~/bc5-work/BOX-LOCK 2>/dev/null; do sleep 5; done; sleep 10; kill $JP; echo "== stream ended $(date +%T)"' > "$STREAM" 2>&1 ) &
timeout $((SECS + 700)) ssh -n bc250 'pgrep "^kyty_emulator" >/dev/null && { echo "EMULATOR RUNS: stop"; exit 1; }; [ -s ~/bc5-work/BOX-LOCK ] && { echo "LOCKED: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }; W=$HOME/bc5-work; cd $W/exp0360 && { '"$PRE"'; } && env '"$ENVS"' ./run0360.sh 41a5a36fffb4f8d4 '"$TAG $SECS"' on 2>&1; echo "run exit $?"; echo "lock: [$(cat $W/BOX-LOCK)]"; pgrep -a "^kyty_emulator" | cut -c1-100 || echo "no emulator"'
wait
echo "$(date +%T) done"
