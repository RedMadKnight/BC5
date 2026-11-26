#!/usr/bin/env bash
# BC5 exp 0391: exp 0372's software replug test (raw/replug0372.sh, 2026-10-29) on the shared normal build, under run0391.sh's
# token lock. While s6n0391.sh runs the second title (RT on, the S6N route), this turns the DualSense's PipeWire card profile
# off and back on: the pad's sink node goes and comes back as at a USB replug, so SDL's PipeWire backend sends the same audio
# device removal and addition (the pad's HID side stays). Test plan A's three pulls: 5 s, under 1 s, 30 s; before and after
# each, the emulator's streams and their links. The profile is set with `pw-cli set-param` without `save` (WirePlumber
# stores nothing); the original index is put back at the end, on failure too. The default sink is muted for the run and its
# mute state put back. With `late`: the profile is off before the run starts and turned on at ~170 s, then one 5-s pull.
# What differs from replug0372.sh (marked "0391:"): the run is recognised by its exact lock line (E0391_LOCKLINE) and the
# emulator by the D19_OWNER token in its environment; private paths under ~/bc5-work/exp0413r/run.
# Started by run0391.sh with the token; usage: replug0391.sh <tag> [pulls|late]   (waits up to 3 min for the run)
set -u
TAG=${1:?tag}; MODE=${2:-pulls}; W=${D19_WORK:-$HOME/bc5-work}; E=$W/exp0413r/run; R=$E/raw; LOCK=$W/BOX-LOCK; LOG=$E/play-last.log
OWNER=${D19_OWNER:?}; LOCKLINE=${E0391_LOCKLINE:?}  # 0391: the run's token and lock line
case "$MODE" in pulls | late) ;; *) echo "mode is pulls or late"; exit 1 ;; esac
PY=$(cd "$(dirname "$0")" && pwd)/streams0391.py
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
OUT=$R/$TAG-replug.txt
[ -e "$OUT" ] && { echo "$OUT exists: tag used"; exit 1; }
say() { echo "$(date +%T.%3N) $*" | tee -a "$OUT"; }
ours() { [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ]; }  # 0391: the exact line
# 0391: the emulator that carries this run's token; a foreign one is never ours
emu() { local p; for p in $(pgrep -x kyty_emulator); do tr '\0' '\n' < "/proc/$p/environ" 2> /dev/null | grep -qxF -- "D19_OWNER=$OWNER" && { echo "$p"; return 0; }; done; return 1; }
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
ours && emu > /dev/null || { say "no s6n0391.sh run under this lock line: nothing done"; exit 1; }
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
