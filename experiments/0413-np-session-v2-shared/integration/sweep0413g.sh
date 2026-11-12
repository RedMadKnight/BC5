#!/usr/bin/env bash
# BC5 exp 0413: ASTRO BOT starts of the private build with the set-buffer guard, over a list of dummy-variable counts
# (BC5_DUMMY_nn=1 in the starting environment: the count moves the leftover registers, README "The cause"). Each start
# goes through start0413g.sh (start0413l.sh with the shortest run lowered to 20 s; the crash came 5-6 s in), which
# takes and releases BOX-LOCK itself. After each start: its end line, the guard's refusal lines and any crash line.
# Stops at the first start that could not be made (an emulator, a lock, a wrong binary).
# usage (on the box): P_BIN=<binary> P_WANT=<md5> sweep0413g.sh <tag prefix> <seconds> "<counts>" [KEY=VALUE ...]
set -u
ulimit -c 0
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd); R=$HOME/bc5-work/exp0413/n/raw
PRE=${1:?a tag prefix}; SECS=${2:?seconds}; COUNTS=${3:?counts}; shift 3
: "${P_BIN:?the binary}" "${P_WANT:?its md5}"
for n in $COUNTS; do
    args=()
    i=1
    while [ "$i" -le "$n" ]; do args+=("$(printf 'BC5_DUMMY_%02d=1' "$i")"); i=$((i + 1)); done
    tag="${PRE}${n}"
    out=$(bash "$HERE/start0413g.sh" "$tag" astro "$SECS" "${args[@]}" "$@" 2>&1 | tail -1)
    [ -e "$R/$tag-end.txt" ] || { echo "$tag NOT MADE: $out"; exit 1; }
    g=$(grep -a -c "exp 0413: set-buffer with the map signature" "$R/$tag-play.log" 2> /dev/null)
    echo "n=$n: $out; guard lines ${g:-0}"
    grep -a -m2 "exp 0413: set-buffer with the map signature" "$R/$tag-play.log" 2> /dev/null | cut -c1-260
    sleep 2
done
echo "sweep $PRE done $(date +%T)"
