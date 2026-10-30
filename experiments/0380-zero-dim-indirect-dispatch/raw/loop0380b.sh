#!/usr/bin/env bash
# BC5 experiment 0380 (§29's B loop): back-to-back S6N tries on the recorder binary 44417414 (s6n0380r1.sh, RT on,
# BC5_CRASH_FRAMES=1 BC5_0380_REC=1, no other exp 0380 switch) until the first try that does not pass, a stop file,
# low disk or the time budget. A B (F403) ends in a gpu-watch reboot: every try's start and verdict line is synced to
# loop.log first, so the log after the reboot says which try it was.
# usage: loop0380b.sh <expected live-saves sum> <tag prefix> [budget s, 7200] [secs per try, 180]   (on the box)
#        touch ~/bc5-work/exp0380r1/run/loop-stop to end after the running try.
set -u
SAVES=${1:?the live saves sum}; PFX=${2:?a tag prefix}; BUDGET=${3:-7200}; SECS=${4:-180}
W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; E=$W/exp0380r1/run; R=$E/raw; S6N=${BC5_0380_S6N:-$W/exp0380r1/s6n0380r1.sh}
LOG=$E/loop-$PFX.log; STOP=$E/loop-stop; DONE=$E/loop-done
case "$PFX" in *[!A-Za-z]* | "") echo "the prefix is letters"; exit 1 ;; esac
[ -x "$S6N" ] || { echo "no $S6N"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: not started"; exit 1; }
[ -s "$LOCK" ] && ! grep -q '^top exp 0380 |' "$LOCK" && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -e "$LOG" ] && { echo "$LOG exists: a new prefix"; exit 1; }
rm -f "$STOP" "$DONE"; mkdir -p "$R"
lock() { echo "top exp 0380 | B loop $PFX, S6N tries of $SECS s RT on, recorder ${BC5_0380_WANT:-44417414}, until a B or $((BUDGET / 60)) min | $(date '+%F %T')" > "$LOCK"; }
note() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; sync; }
trap 'touch "$DONE"; grep -q "^top exp 0380 |" "$LOCK" 2> /dev/null && : > "$LOCK"; sync' EXIT
T0=$(date +%s); i=0; WHY=""
note "loop $PFX start: budget $BUDGET s, $SECS s per try, boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
while :; do
  [ -e "$STOP" ] && { WHY="stop file"; break; }
  [ $(($(date +%s) - T0 + SECS + 60)) -le "$BUDGET" ] || { WHY="time budget"; break; }
  FREE=$(df -Pk "$W" | awk 'NR == 2 {print int($4 / 1048576)}')
  [ "$FREE" -ge 20 ] || { WHY="disk: $FREE GiB free"; break; }
  i=$((i + 1)); TAG=$PFX$(printf %02d "$i")
  lock
  note "try $TAG start ($FREE GiB free, MemAvailable $(awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo) MiB)"
  BC5_0368_SWITCHES="BC5_CRASH_FRAMES=1 BC5_0380_REC=1" bash "$S6N" "$SAVES" "$TAG" "$SECS" on > "$R/$TAG-runner.out" 2>&1
  V=$(cat "$R/$TAG-verdict.txt" 2> /dev/null || echo "no verdict (runner: $(tail -1 "$R/$TAG-runner.out"))")
  note "try $TAG verdict: $V"
  grep -q "THE LIVE SAVES ARE NOT" "$R/$TAG-runner.out" && { WHY="the live saves changed"; break; }
  [ "$V" = pass ] || { WHY="try $TAG: $V"; break; }
  pgrep '^kyty_emulator' > /dev/null && { WHY="an emulator still runs after $TAG"; break; }
  sleep 20
done
note "loop $PFX end after $i tries, $(($(date +%s) - T0)) s: $WHY"
