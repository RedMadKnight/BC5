#!/usr/bin/env bash
# BC5 exp 0418: one run of the second title on exp 0418's private build with the /dev/gc caller trace
# (BC5_GC_IOCTL_TRACE=1; nothing else of 0418 is on: the start-state table and the GS rings stay off). It goes through
# exp 0413's runner run0413p.sh, unchanged: its own atomic BOX-LOCK claim, RT on, the private save copy reset from exp
# 0412's named snapshot, the walk to G+<play>, its sampler, fuse and watchdog. Around it, chk0417g.sh's pad recording:
# evtest writes every key press of every joystick (the runner's own keys do not pass through evdev, so every line is a
# person's or a device's). Afterwards the trace lines are copied out of the run's log into ~/bc5-work/exp0418/raw.
# Writes: ~/bc5-work/exp0413/n/raw/<tag>-* (the runner's own files) and ~/bc5-work/exp0418/raw/<tag>-*.
# The kernel log is streamed by the laptop; the run is stopped there at the first amdgpu error line.
# usage (on the box): run0418.sh <tag t418a..t418z> [play seconds after G, default 240]
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0418; N=$W/exp0413/n; R=$N/raw; O=$E/raw
TAG=${1:?a tag}; PLAY=${2:-240}
case "$TAG" in t418[a-z]) ;; *) echo "run0418: the tag is t418 and one letter: not started"; exit 1 ;; esac
case "$PLAY" in *[!0-9]* | "") echo "run0418: the play time is seconds: not started"; exit 1 ;; esac
BIN=$E/bin/kyty_emulator
[ -x "$BIN" ] && [ -s "$E/built.md5" ] || { echo "run0418: no exp 0418 build: not started"; exit 1; }
WANT=$(md5sum < "$BIN" | cut -d' ' -f1)
grep -qxF "$WANT  bin/kyty_emulator" "$E/built.md5" || { echo "run0418: bin/kyty_emulator is not the one mk0418.sh placed: not started"; exit 1; }
[ -x "$N/run0413p.sh" ] || [ -f "$N/run0413p.sh" ] || { echo "run0418: no run0413p.sh in $N: not started"; exit 1; }
[ -s "$N/words0413nz.txt" ] || { echo "run0418: no words0413nz.txt in $N: not started"; exit 1; }
[ -e "$R/$TAG-end.txt" ] || [ -e "$O/$TAG-runner.out" ] && { echo "run0418: the tag $TAG was used: not started"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "run0418: an emulator runs: not started"; exit 1; }
mkdir -p "$O" || exit 1
PADS=()
padstop() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "${USER:-$(id -un)}" -x evtest 2> /dev/null; }
trap padstop EXIT
: > "$O/$TAG-pad.txt"
n=0
for d in /dev/input/by-id/*-event-joystick; do
    [ -e "$d" ] || continue
    n=$((n + 1))
    stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$O/$TAG-pad.txt" &
    PADS+=($!)
done
T0=$(date +%s)
echo "run0418 $TAG: binary $WANT, play $PLAY s after G, $n joystick(s) watched, start $(date '+%F %T')"
(cd "$N" && P_BIN="$BIN" P_WANT="$WANT" P_WORDS="$N/words0413nz.txt" bash ./run0413p.sh "$TAG" nozeroskip "$PLAY" BC5_GC_IOCTL_TRACE=1) > "$O/$TAG-runner.out" 2>&1
RC=$?
padstop
LINE=$(grep "^$TAG " "$O/$TAG-runner.out" | tail -1)
PADN=$(grep -c . "$O/$TAG-pad.txt")
PADF=$( [ "$PADN" = 0 ] || awk -v t0="$T0" '{ sub(",", "", $3); printf " (first %.0f s after the start)", $3 - t0; exit }' "$O/$TAG-pad.txt")
L=$R/$TAG-play.log
if [ -s "$L" ]; then
    nice -n 19 grep -a 'bc5-gc-trace\|bc5-direct: start state (exp 0418)\|bc5-direct: /dev/gc ' "$L" > "$O/$TAG-trace.txt"
    CODES=$(grep -a -o '\[bc5-gc-trace\] ioctl 0x[0-9a-f]*' "$O/$TAG-trace.txt" | sort -u | wc -l)
    CALLS=$(grep -a -c '\[bc5-gc-trace\] ioctl 0x' "$O/$TAG-trace.txt")
    FR=$(grep -a -c ' frame [0-9]* 0x' "$O/$TAG-trace.txt"); SC=$(grep -a -c ' scan [0-9]* 0x' "$O/$TAG-trace.txt")
    EX=$(grep -a -c ' export ' "$O/$TAG-trace.txt"); PR=$(grep -a -c ' pair [0-9]* 0x' "$O/$TAG-trace.txt")
    TRACE="trace: $CODES request codes, $CALLS calls, $FR frame lines, $SC scan lines, $EX with an export, $PR pair lines"
else
    : > "$O/$TAG-trace.txt"; TRACE="trace: no play log at $L"
fi
echo "run0418 $TAG: runner exit $RC; ${LINE:-no summary line from the runner}"
echo "run0418 $TAG: $TRACE; pad key presses $PADN$PADF; end $(date '+%F %T')"
