#!/usr/bin/env bash
# BC5 exp 0372: the software replug test (the top session, 2026-10-29 night, no one at the box). While s6n0372.sh runs the
# second title on the private pad-route build (RT on, the S6N route), this turns the DualSense's PipeWire card profile
# off and back on: the pad's sink node goes and comes back as at a USB replug, so SDL's PipeWire backend sends the same
# audio device removal and addition (the pad's HID side stays; the maintainer's real replug test is still to come).
# Test plan A's three pulls: 5 s, under 1 s, 30 s; before and after each, the emulator's streams and their links.
# The profile is set with `pw-cli set-param` without `save` (WirePlumber stores nothing); the original index is put back
# at the end, on failure too. The default sink is muted for the run (nobody listens at night) and its mute state put back.
# With `late` (test plan D, a DualSense that comes after the start): the profile is off before the run starts and turned
# on at ~170 s, then one 5-s pull.
# usage: replug0372.sh <tag> [late]   (on the box host, attended; started first, it waits up to 3 min for s6n0372.sh <..> <tag>)
set -u
TAG=${1:?tag}; MODE=${2:-pulls}; W=$HOME/bc5-work; E=$W/exp0372; R=$E/raw; LOCK=$W/BOX-LOCK; LOG=$E/play-last.log
case "$MODE" in pulls | late) ;; *) echo "mode is pulls or late"; exit 1 ;; esac
PY=$(cd "$(dirname "$0")" && pwd)/streams0372.py
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
OUT=$R/$TAG-replug.txt
[ -e "$OUT" ] && { echo "$OUT exists: tag used"; exit 1; }
say() { echo "$(date +%T.%3N) $*" | tee -a "$OUT"; }
ours() { grep -q "^top exp 0372 | s6n run: .*, $TAG, " "$LOCK" 2> /dev/null; }
emu() { pgrep -o -x kyty_emulator; }
read -r DEV PIDX PNAME <<< "$(pw-dump | python3 "$PY" device)"
[ -n "${DEV:-}" ] && [ "$PIDX" != "?" ] || { say "no DualSense ALSA card in PipeWire: not started"; exit 1; }
[ "$PIDX" != 0 ] || { say "the DualSense profile is already off: not started"; exit 1; }
SINK=$(wpctl inspect @DEFAULT_AUDIO_SINK@ | sed -n '1s/^id \([0-9]*\),.*/\1/p')
MUTED=0; wpctl get-volume "$SINK" | grep -q MUTED && MUTED=1
say "tag $TAG: DualSense card $DEV profile $PIDX ($PNAME); default sink $SINK muted=$MUTED"
setprof() { pw-cli set-param "$DEV" Profile "{ index: $1 }" > /dev/null 2>&1; say "profile -> $1 ($(pw-dump "$DEV" | python3 -c 'import json,sys; o=json.load(sys.stdin)[0]; p=o["info"]["params"].get("Profile") or [{}]; print(p[0].get("index"), p[0].get("name"))' 2> /dev/null))"; }
restore() {
  read -r _ NOW _ <<< "$(pw-dump | python3 "$PY" device)"
  [ "${NOW:-}" = "$PIDX" ] || setprof "$PIDX"
  [ "$MUTED" = 1 ] || wpctl set-mute "$SINK" 0
  say "restored: DualSense profile $(pw-dump | python3 "$PY" device | cut -d' ' -f2-), default sink $SINK $(wpctl get-volume "$SINK")"
}
trap restore EXIT
wpctl set-mute "$SINK" 1 && say "default sink $SINK muted for the run"
[ "$MODE" = late ] && { setprof 0; say "late mode: the DualSense's audio is off before the start"; }
NL=0
reads() {
  say "== $1 (emulator up $(ps -o etimes= -p "$(emu)" 2> /dev/null | tr -d ' ') s)"
  pw-dump | python3 "$PY" streams | tee -a "$OUT"
  local n; n=$(grep -a -c . "$LOG" 2> /dev/null); n=${n:-0}
  [ "$n" -gt "$NL" ] && tail -n +"$((NL + 1))" "$LOG" | grep -a -E "AudioOut \(exp 0372\)|pad route:|\(pad\)" | cut -c1-260 | tee -a "$OUT"
  NL=$n
}
# 1. Wait for this tag's run and the pad ports' opens (at most 3 min for the lock, 6 min for the opens).
for _ in $(seq 1 90); do ours && emu > /dev/null && break; sleep 2; done
ours && emu > /dev/null || { say "no s6n0372.sh run with tag $TAG: nothing done"; exit 1; }
for _ in $(seq 1 180); do
  ours && emu > /dev/null || { say "the run ended before the pad ports opened"; exit 1; }
  up=$(ps -o etimes= -p "$(emu)" | tr -d ' ')
  { [ "$MODE" = late ] || grep -a -q "AudioOut (exp 0372): .* type 10: opened" "$LOG" 2> /dev/null; } && [ "${up:-0}" -ge 170 ] && break
  sleep 2
done
[ "$MODE" = late ] || grep -a -q "AudioOut (exp 0372): .* type 10: opened" "$LOG" || say "no type-10 open line by now: going on anyway"
reads "R0 before the first pull"
step() { ours && emu > /dev/null || { say "the run ended: stop"; exit 1; }; }
if [ "$MODE" = late ]; then
  step; setprof "$PIDX"; sleep 5; reads "R2 5 s after the late plug"; sleep 30; reads "35 s after the late plug"
  step; setprof 0; sleep 2; reads "R1 2 s into a 5-s pull"; sleep 3; setprof "$PIDX"; sleep 5; reads "R2 5 s after the 5-s pull"
  sleep 20; reads "R3 25 s after the 5-s pull"
  say "sequence done"; exit 0
fi
# 2. A 5-s pull.
step; setprof 0; sleep 2; reads "R1 2 s into the 5-s pull"; sleep 3; setprof "$PIDX"; sleep 5; reads "R2 5 s after the 5-s pull"
sleep 30; reads "30 s after the 5-s pull"
# 3. A pull under a second.
step; setprof 0; sleep 0.4; setprof "$PIDX"; sleep 5; reads "R2 5 s after the short pull"
sleep 30; reads "30 s after the short pull"
# 4. A 30-s pull.
step; setprof 0; sleep 15; reads "R1 15 s into the 30-s pull"; sleep 15; setprof "$PIDX"; sleep 5; reads "R2 5 s after the 30-s pull"
sleep 20; reads "R3 25 s after the 30-s pull"
say "sequence done"
