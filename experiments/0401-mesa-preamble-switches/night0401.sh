#!/usr/bin/env bash
# BC5 experiment 0401, the night tests of 2026-11-04 (laptop side): runs the arms of a list one after another on the box
# through run0401t.sh, each with the kernel log streamed to the laptop (bounded on both ends: the box's journalctl under
# its own timeout, so no orphan outlives the arm). A GPU hang may reboot the box (the watchdog); then this waits for it to
# come back, removes only our own lock line of that arm if the reboot left it (no emulator runs then), and goes on.
# Results (text only, never the play log or the journal) come to raw/night/.
# arms file: one arm per line, "MODE TAG CAP PLAY BINARY MD5 [KEY=VALUE ...]"; lines starting with # are skipped.
# usage (laptop): bash night0401.sh <the named snapshot's sum (run0401t.sh MODE=name), LC_ALL=C> <arms file>
set -u
SUM=${1:?the named snapshot sum}; ARMS=${2:?an arms file}
HERE=$(cd "$(dirname "$0")" && pwd); OUT=$HERE/raw/night; mkdir -p "$OUT"
SSH=(ssh -n -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=30 bc250)   # -n: never read the arms file
SSHI=(ssh -o ConnectTimeout=10 -o BatchMode=yes bc250)   # for a script on stdin
up() { timeout 25 "${SSH[@]}" true 2> /dev/null; }
wait_up() { local i; for i in $(seq 1 40); do up && return 0; sleep 30; done; return 1; }
while read -r MODE TAG CAP PLAY BIN MD5 REST; do
  case "$MODE" in "" | \#*) continue ;; esac
  echo "== $(date '+%F %T') arm $TAG ($MODE, cap $CAP s, play $PLAY s)" | tee -a "$OUT/night.txt"
  wait_up || { echo "the box does not answer: stop" | tee -a "$OUT/night.txt"; exit 1; }
  if ! timeout 25 "${SSH[@]}" 'pgrep "^kyty_emulator" > /dev/null && exit 1; [ ! -s ~/bc5-work/BOX-LOCK ]'; then
    echo "the box is busy or locked: $(timeout 25 "${SSH[@]}" 'cat ~/bc5-work/BOX-LOCK; pgrep -l "^kyty_emulator"' 2>&1 | head -3): stop" | tee -a "$OUT/night.txt"; exit 1
  fi
  timeout $((CAP + 420)) "${SSH[@]}" "timeout $((CAP + 400)) journalctl -k -f -n 0 -o short-precise" > "$OUT/$TAG-kernel-stream.txt" 2>&1 &
  KS=$!
  # shellcheck disable=SC2086
  timeout $((CAP + 900)) "${SSH[@]}" "MODE=$MODE bash ~/bc5-work/exp0401t/run0401t.sh $SUM $TAG $CAP $PLAY $BIN $MD5 $REST" > "$OUT/$TAG-run.txt" 2>&1
  RC=$?
  kill "$KS" 2> /dev/null; wait "$KS" 2> /dev/null
  echo "run rc $RC: $(tail -2 "$OUT/$TAG-run.txt" | tr '\n' ' ' | cut -c1-400)" | tee -a "$OUT/night.txt"
  if ! up; then
    echo "$(date '+%T') the box does not answer after the arm (a reboot?): waiting" | tee -a "$OUT/night.txt"
    wait_up || { echo "the box did not come back: stop" | tee -a "$OUT/night.txt"; exit 1; }
    sleep 60   # autologin and the desktop
  fi
  # A reboot during the arm leaves our lock line behind: remove exactly that line, and only with no emulator running.
  timeout 25 "${SSHI[@]}" 'bash -s' "$TAG" << 'EOS' 2>&1 | tee -a "$OUT/night.txt"
TAG=$1
pgrep '^kyty_emulator' > /dev/null && exit 0
L=$HOME/bc5-work/BOX-LOCK
grep -q "^water exp 0401t | arm $TAG (" "$L" 2> /dev/null || exit 0
grep -v "^water exp 0401t | arm $TAG (" "$L" > "$L.0401t-fix"; mv -fT "$L.0401t-fix" "$L"
echo "water exp 0401t | released after a reboot: arm $TAG | $(date '+%F %T')" >> "$HOME/bc5-work/BOX-QUEUE"
echo "stale lock line of $TAG removed"
EOS
  for f in summary end start switch-lines crash probe memline route freeze-watch dmesg-after devcoredump journal io; do   # io: exp 0401 e10
    timeout 30 "${SSH[@]}" "cat ~/bc5-work/exp0401t/raw/$TAG-$f.txt 2> /dev/null | head -c 400000" > "$OUT/$TAG-$f.txt" 2> /dev/null
  done
  timeout 30 "${SSH[@]}" "ls -la ~/bc5-work/exp0401t/raw/freeze-$TAG 2> /dev/null; head -c 200000 ~/bc5-work/exp0401t/raw/freeze-$TAG/* 2> /dev/null" > "$OUT/$TAG-freeze-dumps.txt" 2> /dev/null
  echo "summary: $(cat "$OUT/$TAG-summary.txt" 2> /dev/null | cut -c1-400)" | tee -a "$OUT/night.txt"
done < "$ARMS"
echo "== $(date '+%F %T') all arms done" | tee -a "$OUT/night.txt"
