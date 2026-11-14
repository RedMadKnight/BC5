#!/usr/bin/env bash
# BC5 exp 0419, phase 2, batch 3, round 1 (laptop): decides the level of mkfold0419.py for each library file.
# For each file: the errors of the laptop's syntax check before any change (the baseline; most files have none), then
# levels 7, 5, 3, 1 in turn on a fresh copy; the first level whose errors are the baseline's is the file's level, else 0.
# The check is -fsyntax-only -std=c++20 -Wall -Wextra -Werror with the stand-ins of exp 0401's lib0405 check (chk.sh).
# usage: mklevels0419.sh <git worktree at build U> <chk.sh> <python> <out levels file>
set -u
T=$1; CHK=$2; PY=$3; OUT=$4; HERE=$(cd "$(dirname "$0")" && pwd)
FILES="libs/libAudio.cpp libs/libCamera.cpp libs/libCompanion.cpp libs/libDiscMap.cpp libs/libGameLiveStreaming.cpp libs/libHmd.cpp libs/libInvitationDialog.cpp libs/libMove.cpp libs/libNet.cpp libs/libNp.cpp libs/libScreenShot.cpp libs/libSharePlay.cpp libs/libUlobjmgr.cpp libs/libUsbd.cpp libs/libVoice.cpp libs/libVrTracker.cpp libs/libWebBrowserDialog.cpp"
norm() { grep -E 'error:' | sed -E 's/^.*:[0-9]+:[0-9]+: //' | LC_ALL=C sort; }
echo "# mkfold0419.py levels, decided by mklevels0419.sh on the laptop against build U ($(date '+%F'))" > "$OUT"
for f in $FILES; do
    (cd "$T" && git checkout -q -- "src/$f")
    base=$(bash "$CHK" "$T/src" "$f" 2>&1 | norm)
    got=0
    for lv in 7 5 3 1; do
        (cd "$T" && git checkout -q -- "src/$f")
        "$PY" "$(cygpath -w "$HERE/mkfold0419.py")" "$(cygpath -w "$T")" one "$f" "$lv" > /dev/null 2>&1 || continue
        now=$(bash "$CHK" "$T/src" "$f" 2>&1 | norm)
        if [ "$now" = "$base" ]; then got=$lv; break; fi
    done
    (cd "$T" && git checkout -q -- "src/$f")
    echo "$got $f" >> "$OUT"
    echo "$f: level $got (baseline errors: $(printf '%s' "$base" | grep -c . ))"
done
